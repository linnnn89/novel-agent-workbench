from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chapters import ChapterWorkflowService
from .providers import MOCK_PROVIDER_ID, ProviderRequest, generate_with_provider, get_model_role_config
from .storage import ProjectStore, safe_filename, utc_stamp


DRAFTS_DIRNAME = "drafts"
DRAFTS_INDEX_FILENAME = "drafts_index.json"
CONFIRMED_CHAPTERS_DIRNAME = "confirmed_chapters"
CONFIRMED_CHAPTERS_INDEX_FILENAME = "confirmed_chapters.json"
COMMIT_LOG_FILENAME = "commit_log.json"


class DraftGenerationError(RuntimeError):
    """Raised when draft generation cannot safely produce a draft."""


@dataclass(frozen=True, slots=True)
class DraftGenerationRequest:
    chapter_id: str
    prompt: str
    title: str = ""
    system_prompt: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_chapter_id(self.chapter_id)
        if not self.prompt.strip():
            raise DraftGenerationError("prompt cannot be empty.")

    def to_provider_request(self) -> ProviderRequest:
        metadata = {
            **self.metadata,
            "chapter_id": self.chapter_id,
            "draft_generation": True,
        }
        return ProviderRequest(
            role="writer",
            prompt=self.prompt,
            system_prompt=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DraftGenerationResult:
    draft_id: str
    chapter_id: str
    title: str
    path: str
    provider: str
    model: str
    usage: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DraftCommitResult:
    draft_id: str
    chapter_id: str
    title: str
    path: str
    committed_at: str
    checkpoint: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DraftGenerationService:
    """Backend-only service that writes provider output as draft artifacts."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def drafts_dir(self) -> Path:
        return self.store.data_dir / DRAFTS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / DRAFTS_INDEX_FILENAME

    @property
    def confirmed_dir(self) -> Path:
        return self.store.data_dir / CONFIRMED_CHAPTERS_DIRNAME

    @property
    def confirmed_index_path(self) -> Path:
        return self.store.data_dir / CONFIRMED_CHAPTERS_INDEX_FILENAME

    @property
    def commit_log_path(self) -> Path:
        return self.store.data_dir / COMMIT_LOG_FILENAME

    def generate_draft(self, request: DraftGenerationRequest) -> DraftGenerationResult:
        self.store.initialize()
        with self.store.lock():
            title = request.title.strip()
            workflow = ChapterWorkflowService(self.store)
            workflow.mark_drafting(request.chapter_id, title=title)
            try:
                response = generate_with_provider(self.store, request.to_provider_request())
                draft_id = new_draft_id()
                created_at = utc_stamp()
            except Exception as exc:
                workflow.record_error(
                    request.chapter_id,
                    title=title,
                    stage="generate_draft",
                    error_type=getattr(exc, "error_type", exc.__class__.__name__),
                    message=str(exc),
                )
                raise
            draft_path = self.drafts_dir / f"{safe_filename(request.chapter_id)}__{draft_id}.json"
            artifact = {
                "schema_version": 1,
                "status": "draft",
                "draft_id": draft_id,
                "chapter_id": request.chapter_id,
                "title": title,
                "created_at": created_at,
                "content": response.text,
                "provider": {
                    "role": "writer",
                    "provider": response.provider,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                },
                "request_summary": {
                    "prompt_chars": len(request.prompt),
                    "system_prompt_chars": len(request.system_prompt or ""),
                    "metadata_keys": sorted(str(key) for key in request.metadata),
                },
            }
            self.store.write_json(draft_path, artifact)
            self._append_index_entry(
                {
                    "draft_id": draft_id,
                    "chapter_id": request.chapter_id,
                    "title": title,
                    "created_at": created_at,
                    "status": "draft",
                    "path": str(draft_path.relative_to(self.store.root)),
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage,
                }
            )
            workflow.mark_draft_ready(request.chapter_id, title=title, draft_id=draft_id)
            return DraftGenerationResult(
                draft_id=draft_id,
                chapter_id=request.chapter_id,
                title=title,
                path=str(draft_path),
                provider=response.provider,
                model=response.model,
                usage=response.usage,
            )

    def generate_context_draft(
        self,
        request: DraftGenerationRequest,
        *,
        max_context_tokens: int | None = None,
    ) -> DraftGenerationResult:
        from .context_assembler import ContextAssemblerService

        role_config = get_model_role_config(self.store, "writer")
        if role_config.provider != MOCK_PROVIDER_ID:
            raise DraftGenerationError("Context-aware draft generation is mock-only in this phase.")
        render = ContextAssemblerService(self.store).prompt_render_dry_run(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            max_context_tokens=max_context_tokens,
            include_prompt_text=True,
            include_context_text=True,
        ).to_dict()
        rendered_prompt = render_context_prompt(render)
        context_request = DraftGenerationRequest(
            chapter_id=request.chapter_id,
            title=request.title,
            prompt=rendered_prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            metadata={**request.metadata, "context_aware_generation": True},
        )
        result = self.generate_draft(context_request)
        self._write_context_generation_summary(result.draft_id, render)
        return result

    def list_drafts(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        if not isinstance(index, dict):
            return []
        drafts = index.get("drafts")
        if not isinstance(drafts, list):
            return []
        return [item for item in drafts if isinstance(item, dict)]

    def get_draft_status(self, draft_id: str) -> str:
        draft = self.read_draft(draft_id)
        return str(draft.get("status") or "")

    def read_draft(self, draft_id: str) -> dict[str, Any]:
        for item in self.list_drafts():
            if item.get("draft_id") != draft_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise DraftGenerationError(f"Draft index entry has no path: {draft_id}")
            draft = self.store.read_json(path, default=None)
            if not isinstance(draft, dict):
                raise DraftGenerationError(f"Draft artifact is missing or invalid: {draft_id}")
            return draft
        raise DraftGenerationError(f"Draft not found: {draft_id}")

    def commit_draft(self, draft_id: str) -> DraftCommitResult:
        self.store.initialize()
        with self.store.lock():
            chapter_id = ""
            title = ""
            workflow = ChapterWorkflowService(self.store)
            try:
                draft_entry = self._draft_index_entry(draft_id)
                draft = self.read_draft(draft_id)
                chapter_id = str(draft.get("chapter_id") or "").strip()
                validate_chapter_id(chapter_id)
                title = str(draft.get("title") or "")
                if draft.get("status") != "draft" or draft_entry.get("status") != "draft":
                    raise DraftGenerationError(f"Draft is not committable: {draft_id}")
                confirmed_index = self._read_confirmed_index()
                if any(item.get("chapter_id") == chapter_id for item in confirmed_index):
                    raise DraftGenerationError(f"Confirmed chapter already exists: {chapter_id}")

                checkpoint = self.store.create_checkpoint(label="pre_commit")
                committed_at = utc_stamp()
                provider = draft.get("provider") if isinstance(draft.get("provider"), dict) else {}
                artifact_path = self.confirmed_dir / f"{safe_filename(chapter_id)}.json"
                artifact = {
                    "schema_version": 1,
                    "chapter_id": chapter_id,
                    "title": title,
                    "content": str(draft.get("content") or ""),
                    "source_draft_id": draft_id,
                    "committed_at": committed_at,
                    "provider": {
                        "provider": str(provider.get("provider") or ""),
                        "model": str(provider.get("model") or ""),
                        "usage": provider.get("usage") if isinstance(provider.get("usage"), dict) else {},
                    },
                    "future_hooks": {
                        "memory_bank_update": "not_implemented",
                        "rag_update": "not_implemented",
                        "export_update": "not_implemented",
                    },
                }
                confirmed_entry = {
                    "chapter_id": chapter_id,
                    "title": title,
                    "source_draft_id": draft_id,
                    "committed_at": committed_at,
                    "path": str(artifact_path.relative_to(self.store.root)),
                    "provider": artifact["provider"]["provider"],
                    "model": artifact["provider"]["model"],
                    "usage": artifact["provider"]["usage"],
                }
                self.store.write_json(artifact_path, artifact)
                self._append_confirmed_entry(confirmed_entry)
                self._update_draft_status(draft_id, status="committed", committed_at=committed_at, chapter_id=chapter_id)
                self._append_commit_log(
                    {
                        "commit_id": f"{committed_at}_{uuid4().hex[:12]}",
                        "timestamp": committed_at,
                        "draft_id": draft_id,
                        "chapter_id": chapter_id,
                        "status": "committed",
                        "provider": artifact["provider"]["provider"],
                        "model": artifact["provider"]["model"],
                        "usage": artifact["provider"]["usage"],
                        "checkpoint_id": checkpoint.get("checkpoint_id"),
                    }
                )
                workflow.mark_committed(
                    chapter_id,
                    title=title,
                    draft_id=draft_id,
                    confirmed_chapter_id=chapter_id,
                )
                return DraftCommitResult(
                    draft_id=draft_id,
                    chapter_id=chapter_id,
                    title=title,
                    path=str(artifact_path),
                    committed_at=committed_at,
                    checkpoint=checkpoint,
                )
            except Exception as exc:
                if chapter_id:
                    workflow.record_error(
                        chapter_id,
                        title=title,
                        stage="commit_draft",
                        error_type=getattr(exc, "error_type", exc.__class__.__name__),
                        message=str(exc),
                    )
                raise

    def list_confirmed_chapters(self) -> list[dict[str, Any]]:
        return self._read_confirmed_index()

    def read_confirmed_chapter(self, chapter_id: str) -> dict[str, Any]:
        validate_chapter_id(chapter_id)
        for item in self._read_confirmed_index():
            if item.get("chapter_id") != chapter_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise DraftGenerationError(f"Confirmed index entry has no path: {chapter_id}")
            chapter = self.store.read_json(path, default=None)
            if not isinstance(chapter, dict):
                raise DraftGenerationError(f"Confirmed chapter is missing or invalid: {chapter_id}")
            return chapter
        raise DraftGenerationError(f"Confirmed chapter not found: {chapter_id}")

    def read_commit_log(self) -> dict[str, Any]:
        log = self.store.read_json(self.commit_log_path, default={"schema_version": 1, "commits": []})
        return log if isinstance(log, dict) else {"schema_version": 1, "commits": []}

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "drafts": []}
        drafts = index.get("drafts") if isinstance(index.get("drafts"), list) else []
        drafts.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "drafts": drafts})

    def _draft_index_entry(self, draft_id: str) -> dict[str, Any]:
        for item in self.list_drafts():
            if item.get("draft_id") == draft_id:
                return item
        raise DraftGenerationError(f"Draft not found: {draft_id}")

    def _update_draft_status(self, draft_id: str, *, status: str, committed_at: str, chapter_id: str) -> None:
        draft_entry = self._draft_index_entry(draft_id)
        draft = self.read_draft(draft_id)
        draft["status"] = status
        draft["committed_at"] = committed_at
        draft["committed_chapter_id"] = chapter_id
        self.store.write_json(str(draft_entry["path"]), draft)

        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        drafts = index.get("drafts") if isinstance(index, dict) and isinstance(index.get("drafts"), list) else []
        updated: list[dict[str, Any]] = []
        for item in drafts:
            if isinstance(item, dict) and item.get("draft_id") == draft_id:
                item = {**item, "status": status, "committed_at": committed_at, "committed_chapter_id": chapter_id}
            if isinstance(item, dict):
                updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "drafts": updated})

    def _read_confirmed_index(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.confirmed_index_path, default={"schema_version": 1, "chapters": []})
        if not isinstance(index, dict):
            return []
        chapters = index.get("chapters")
        if not isinstance(chapters, list):
            return []
        return [item for item in chapters if isinstance(item, dict)]

    def _append_confirmed_entry(self, entry: dict[str, Any]) -> None:
        chapters = self._read_confirmed_index()
        chapters.append(entry)
        self.store.write_json(self.confirmed_index_path, {"schema_version": 1, "chapters": chapters})

    def _append_commit_log(self, entry: dict[str, Any]) -> None:
        log = self.read_commit_log()
        commits = log.get("commits") if isinstance(log.get("commits"), list) else []
        commits.append(entry)
        self.store.write_json(self.commit_log_path, {"schema_version": 1, "commits": commits})

    def _write_context_generation_summary(self, draft_id: str, render: dict[str, Any]) -> None:
        draft_entry = self._draft_index_entry(draft_id)
        draft = self.read_draft(draft_id)
        package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
        sections = package.get("sections") if isinstance(package.get("sections"), list) else []
        skipped = package.get("skipped") if isinstance(package.get("skipped"), list) else []
        summary = {
            "mode": "mock_context_aware_generation",
            "prompt_render_mode": render.get("mode"),
            "context_section_count": len(sections),
            "skipped_context_count": len(skipped),
            "context_source_ids": [str(item.get("source_id") or "") for item in sections if isinstance(item, dict)],
            "prompt_summary": render.get("prompt_summary") if isinstance(render.get("prompt_summary"), dict) else {},
            "provider_called_by_render": False,
            "text_in_artifact_metadata": False,
        }
        draft["context_generation"] = summary
        self.store.write_json(str(draft_entry["path"]), draft)

        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        drafts = index.get("drafts") if isinstance(index, dict) and isinstance(index.get("drafts"), list) else []
        updated: list[dict[str, Any]] = []
        for item in drafts:
            if isinstance(item, dict) and item.get("draft_id") == draft_id:
                item = {
                    **item,
                    "context_aware": True,
                    "context_section_count": summary["context_section_count"],
                }
            if isinstance(item, dict):
                updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "drafts": updated})


def new_draft_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"


def render_context_prompt(render: dict[str, Any]) -> str:
    package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
    sections = package.get("sections") if isinstance(package.get("sections"), list) else []
    lines: list[str] = ["Context package:"]
    for item in sections:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        category_id = str(item.get("category_id") or "uncategorized")
        source_id = str(item.get("source_id") or "")
        lines.append(f"[{category_id} {source_id}]")
        lines.append(text)
    prompt_message = next(
        (
            item
            for item in render.get("rendered_messages", [])
            if isinstance(item, dict) and item.get("label") == "draft_prompt"
        ),
        {},
    )
    prompt = str(prompt_message.get("content") or "").strip()
    lines.append("")
    lines.append("Draft request:")
    lines.append(prompt)
    return "\n".join(lines).strip()


def validate_chapter_id(chapter_id: str) -> None:
    value = chapter_id.strip()
    if not value or value in {".", ".."}:
        raise DraftGenerationError("chapter_id cannot be empty, '.' or '..'.")
    if any(separator in value for separator in ("/", "\\", ":", " ")):
        raise DraftGenerationError(f"Unsafe chapter_id: {chapter_id!r}")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise DraftGenerationError(f"Unsafe chapter_id: {chapter_id!r}")
