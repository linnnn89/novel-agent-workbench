from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .chapters import ChapterWorkflowService
from .providers import MOCK_PROVIDER_ID, ProviderRequest, generate_with_provider, get_model_role_config
from .storage import ProjectStore, retire_path, safe_filename, utc_stamp


DRAFTS_DIRNAME = "drafts"
DRAFTS_INDEX_FILENAME = "drafts_index.json"
CONFIRMED_CHAPTERS_DIRNAME = "confirmed_chapters"
CONFIRMED_CHAPTERS_INDEX_FILENAME = "confirmed_chapters.json"
COMMIT_LOG_FILENAME = "commit_log.json"
REASONING_BLOCK_PATTERN = re.compile(r"<think\b[^>]*>.*?</think\s*>", flags=re.IGNORECASE | re.DOTALL)
REASONING_TAG_PATTERN = re.compile(r"</?think\b[^>]*>", flags=re.IGNORECASE)
NON_COMMITTABLE_ACCEPTED_REVIEW_REASON_CODES = {"smoke_test_only"}


class DraftGenerationError(RuntimeError):
    """Raised when draft generation cannot safely produce a draft."""


class DraftCommitGateError(DraftGenerationError):
    """Raised when a draft is not approved for confirmed-chapter commit."""


@dataclass(frozen=True, slots=True)
class DraftGenerationRequest:
    chapter_id: str
    prompt: str
    title: str = ""
    system_prompt: str = ""
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repetition_penalty: float | None = None
    stream: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    stream_callback: Callable[[str], None] | None = field(default=None, repr=False, compare=False)
    reasoning_callback: Callable[[str], None] | None = field(default=None, repr=False, compare=False)

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
            top_p=self.top_p,
            top_k=self.top_k,
            min_p=self.min_p,
            max_tokens=self.max_tokens,
            presence_penalty=self.presence_penalty,
            frequency_penalty=self.frequency_penalty,
            repetition_penalty=self.repetition_penalty,
            stream=self.stream,
            metadata=metadata,
            stream_callback=self.stream_callback,
            reasoning_callback=self.reasoning_callback,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("stream_callback", None)
        data.pop("reasoning_callback", None)
        return data


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
            chapter_preexisted = any(item.get("chapter_id") == request.chapter_id for item in workflow.list_chapters())
            try:
                stream_callback = stream_sanitizer_callback(request.stream_callback, request.reasoning_callback)
                provider_request = request.to_provider_request()
                if stream_callback is not None:
                    provider_request = replace(provider_request, stream_callback=stream_callback)
                response = generate_with_provider(self.store, provider_request)
                draft_id = new_draft_id()
                created_at = utc_stamp()
            except Exception as exc:
                if chapter_preexisted:
                    workflow.record_error(
                        request.chapter_id,
                        title=title,
                        stage="generate_draft",
                        error_type=getattr(exc, "error_type", exc.__class__.__name__),
                        message=str(exc),
                    )
                raise
            sanitized = sanitize_provider_draft_text(response.text)
            version = self.next_chapter_draft_version(request.chapter_id)
            version_label = f"ver{version}"
            draft_path = self.drafts_dir / f"{safe_filename(request.chapter_id)}__{version_label}__{draft_id}.json"
            artifact = {
                "schema_version": 1,
                "status": "draft",
                "draft_id": draft_id,
                "chapter_id": request.chapter_id,
                "title": title,
                "version": version,
                "version_label": version_label,
                "created_at": created_at,
                "content": sanitized["content"],
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
                    "sampling_keys": sorted(
                        key
                        for key, value in {
                            "temperature": request.temperature,
                            "top_p": request.top_p,
                            "top_k": request.top_k,
                            "min_p": request.min_p,
                            "max_tokens": request.max_tokens,
                            "presence_penalty": request.presence_penalty,
                            "frequency_penalty": request.frequency_penalty,
                            "repetition_penalty": request.repetition_penalty,
                            "stream": request.stream,
                        }.items()
                        if value is not None
                    ),
                    "metadata_keys": sorted(str(key) for key in request.metadata),
                    "response_sanitizer": sanitized["summary"],
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
                    "version": version,
                    "version_label": version_label,
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
        final_assembly_gate_id: str = "",
    ) -> DraftGenerationResult:
        from .context_assembler import ContextAssemblerService

        role_config = get_model_role_config(self.store, "writer")
        render = ContextAssemblerService(self.store).prompt_render_dry_run(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            max_context_tokens=max_context_tokens,
            chapter_id=request.chapter_id,
            include_prompt_text=True,
            include_context_text=True,
        ).to_dict()
        rendered_prompt = render_context_prompt(render)
        metadata = {**request.metadata, "context_aware_generation": True}
        if final_assembly_gate_id:
            metadata["final_assembly_gate_id"] = final_assembly_gate_id
        context_request = DraftGenerationRequest(
            chapter_id=request.chapter_id,
            title=request.title,
            prompt=rendered_prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            min_p=request.min_p,
            max_tokens=request.max_tokens,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
            repetition_penalty=request.repetition_penalty,
            stream=request.stream,
            stream_callback=request.stream_callback,
            reasoning_callback=request.reasoning_callback,
            metadata=metadata,
        )
        result = self.generate_draft(context_request)
        mode = "mock_context_aware_generation" if role_config.provider == MOCK_PROVIDER_ID else "real_context_aware_generation"
        self._write_context_generation_summary(result.draft_id, render, mode=mode)
        return result

    def save_provider_draft_version(
        self,
        *,
        chapter_id: str,
        title: str = "",
        content: str,
        provider_role: str,
        provider: str,
        model: str,
        finish_reason: str = "",
        usage: dict[str, int] | None = None,
        request_summary: dict[str, Any] | None = None,
        artifact_metadata: dict[str, Any] | None = None,
    ) -> DraftGenerationResult:
        self.store.initialize()
        with self.store.lock():
            validate_chapter_id(chapter_id)
            title = str(title or "").strip()
            sanitized = sanitize_provider_draft_text(content)
            draft_id = new_draft_id()
            created_at = utc_stamp()
            version = self.next_chapter_draft_version(chapter_id)
            version_label = f"ver{version}"
            draft_path = self.drafts_dir / f"{safe_filename(chapter_id)}__{version_label}__{draft_id}.json"
            summary = dict(request_summary or {})
            summary["response_sanitizer"] = sanitized["summary"]
            provider_usage = dict(usage or {})
            artifact = {
                "schema_version": 1,
                "status": "draft",
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "title": title,
                "version": version,
                "version_label": version_label,
                "created_at": created_at,
                "content": sanitized["content"],
                "provider": {
                    "role": str(provider_role or ""),
                    "provider": str(provider or ""),
                    "model": str(model or ""),
                    "finish_reason": str(finish_reason or ""),
                    "usage": provider_usage,
                },
                "request_summary": summary,
            }
            reserved_keys = set(artifact)
            for key, value in (artifact_metadata or {}).items():
                if str(key) not in reserved_keys:
                    artifact[str(key)] = value
            self.store.write_json(draft_path, artifact)
            revision = artifact.get("revision") if isinstance(artifact.get("revision"), dict) else {}
            index_entry: dict[str, Any] = {
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "title": title,
                "created_at": created_at,
                "status": "draft",
                "version": version,
                "version_label": version_label,
                "path": str(draft_path.relative_to(self.store.root)),
                "provider": str(provider or ""),
                "model": str(model or ""),
                "usage": provider_usage,
            }
            if revision:
                index_entry.update(
                    {
                        "revision_mode": str(revision.get("mode") or ""),
                        "source_draft_id": str(revision.get("source_draft_id") or ""),
                        "source_review_id": str(revision.get("source_review_id") or ""),
                    }
                )
            self._append_index_entry(index_entry)
            ChapterWorkflowService(self.store).mark_draft_ready(chapter_id, title=title, draft_id=draft_id)
            return DraftGenerationResult(
                draft_id=draft_id,
                chapter_id=chapter_id,
                title=title,
                path=str(draft_path),
                provider=str(provider or ""),
                model=str(model or ""),
                usage=provider_usage,
            )

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

    def verify_draft_index_entry(self, draft_id: str) -> dict[str, Any]:
        entry = self._draft_index_entry(draft_id)
        path = entry.get("path")
        if not isinstance(path, str) or not path.strip():
            return {
                "draft_id": draft_id,
                "ok": False,
                "status": "missing_path",
                "path": "",
                "artifact_exists": False,
            }
        target = self.store._resolve_owned_path(path)
        if not target.exists():
            return {
                "draft_id": draft_id,
                "ok": False,
                "status": "missing_artifact",
                "path": path,
                "artifact_path": str(target),
                "artifact_exists": False,
            }
        draft = self.store.read_json(path, default=None)
        return {
            "draft_id": draft_id,
            "ok": isinstance(draft, dict),
            "status": "ok" if isinstance(draft, dict) else "invalid_artifact",
            "path": path,
            "artifact_path": str(target),
            "artifact_exists": True,
        }

    def remove_missing_draft_index_entries(self, draft_ids: list[str]) -> dict[str, Any]:
        requested = {str(draft_id or "").strip() for draft_id in draft_ids if str(draft_id or "").strip()}
        if not requested:
            return {"removed": [], "skipped": [], "remaining_count": len(self.list_drafts())}
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        drafts = index.get("drafts") if isinstance(index, dict) and isinstance(index.get("drafts"), list) else []
        removed: list[str] = []
        skipped: list[dict[str, str]] = []
        kept: list[dict[str, Any]] = []
        for item in drafts:
            if not isinstance(item, dict):
                continue
            draft_id = str(item.get("draft_id") or "")
            if draft_id not in requested:
                kept.append(item)
                continue
            try:
                check = self.verify_draft_index_entry(draft_id)
            except Exception as exc:
                kept.append(item)
                skipped.append({"draft_id": draft_id, "reason": str(exc)})
                continue
            if check.get("status") == "missing_artifact":
                removed.append(draft_id)
                continue
            kept.append(item)
            skipped.append({"draft_id": draft_id, "reason": str(check.get("status") or "not_missing")})
        self.store.write_json(self.index_path, {"schema_version": 1, "drafts": kept})
        return {"removed": removed, "skipped": skipped, "remaining_count": len(kept)}

    def delete_chapter_drafts(self, chapter_id: str) -> dict[str, Any]:
        validate_chapter_id(chapter_id)
        self.store.initialize()
        with self.store.lock():
            checkpoint = self.store.create_checkpoint(label=f"pre_delete_{chapter_id}_drafts")
            confirmed_entries = [
                item for item in self._read_confirmed_index() if str(item.get("chapter_id") or "") == chapter_id
            ]
            retained_source_draft_ids = {
                str(item.get("source_draft_id") or "") for item in confirmed_entries if item.get("source_draft_id")
            }
            draft_index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
            draft_entries = (
                draft_index.get("drafts")
                if isinstance(draft_index, dict) and isinstance(draft_index.get("drafts"), list)
                else []
            )
            kept_drafts: list[dict[str, Any]] = []
            deleted_draft_ids: set[str] = set()
            skipped_drafts: list[dict[str, str]] = []
            retired_paths: list[str] = []
            for item in draft_entries:
                if not isinstance(item, dict):
                    continue
                if str(item.get("chapter_id") or "") != chapter_id:
                    kept_drafts.append(item)
                    continue
                draft_id = str(item.get("draft_id") or "")
                if draft_id in retained_source_draft_ids:
                    kept_drafts.append(item)
                    skipped_drafts.append({"draft_id": draft_id, "reason": "confirmed_source_draft_retained"})
                    continue
                deleted_draft_ids.add(draft_id)
                retired = retire_indexed_artifact(self.store, item.get("path"))
                if retired:
                    retired_paths.append(retired)
            retired_paths.extend(
                retire_orphan_chapter_artifacts(
                    self.store,
                    self.drafts_dir,
                    f"{safe_filename(chapter_id)}__*.json",
                    retained_source_draft_ids,
                )
            )
            self.store.write_json(self.index_path, {"schema_version": 1, "drafts": kept_drafts})

            removed_reviews = self._delete_related_index_entries(
                index_path=self.store.data_dir / "reviews_index.json",
                list_key="reviews",
                chapter_id=chapter_id,
                draft_ids=deleted_draft_ids,
                retained_draft_ids=retained_source_draft_ids,
                retired_paths=retired_paths,
            )
            removed_revision_requests = self._delete_related_index_entries(
                index_path=self.store.data_dir / "revision_requests_index.json",
                list_key="revision_requests",
                chapter_id=chapter_id,
                draft_ids=deleted_draft_ids,
                retained_draft_ids=retained_source_draft_ids,
                retired_paths=retired_paths,
            )
            workflow = ChapterWorkflowService(self.store)
            if confirmed_entries:
                retained_draft_id = next(iter(retained_source_draft_ids), "")
                title = str(confirmed_entries[0].get("title") or chapter_id)
                workflow.mark_committed(
                    chapter_id,
                    title=title,
                    draft_id=retained_draft_id,
                    confirmed_chapter_id=chapter_id,
                )
            else:
                workflow.remove_chapter(chapter_id)
            return {
                "chapter_id": chapter_id,
                "deleted_draft_ids": sorted(deleted_draft_ids),
                "skipped_drafts": skipped_drafts,
                "removed_reviews": removed_reviews,
                "removed_revision_requests": removed_revision_requests,
                "retired_paths": retired_paths,
                "checkpoint": checkpoint,
                "confirmed_chapter_retained": bool(confirmed_entries),
            }

    def commit_draft(self, draft_id: str, *, replace_existing: bool = False) -> DraftCommitResult:
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
                existing_confirmed = next((item for item in confirmed_index if item.get("chapter_id") == chapter_id), None)
                if existing_confirmed is not None and not replace_existing:
                    raise DraftGenerationError(f"Confirmed chapter already exists: {chapter_id}")
                commit_gate = accepted_review_commit_gate(self.store, draft)

                checkpoint_label = "pre_replace_commit" if existing_confirmed else "pre_commit"
                checkpoint = self.store.create_checkpoint(label=checkpoint_label)
                committed_at = utc_stamp()
                provider = draft.get("provider") if isinstance(draft.get("provider"), dict) else {}
                artifact_path = self.confirmed_dir / f"{safe_filename(chapter_id)}.json"
                artifact = {
                    "schema_version": 1,
                    "chapter_id": chapter_id,
                    "title": title,
                    "content": str(draft.get("content") or ""),
                    "source_draft_id": draft_id,
                    "source_draft_version": safe_positive_int(draft.get("version")),
                    "source_draft_version_label": str(draft.get("version_label") or ""),
                    "committed_at": committed_at,
                    "commit_gate": commit_gate,
                    "replacement": confirmed_replacement_summary(existing_confirmed),
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
                    "source_draft_version": artifact["source_draft_version"],
                    "source_draft_version_label": artifact["source_draft_version_label"],
                    "committed_at": committed_at,
                    "path": str(artifact_path.relative_to(self.store.root)),
                    "provider": artifact["provider"]["provider"],
                    "model": artifact["provider"]["model"],
                    "usage": artifact["provider"]["usage"],
                    "commit_gate": commit_gate,
                    "replacement": artifact["replacement"],
                }
                self.store.write_json(artifact_path, artifact)
                if existing_confirmed is not None:
                    self._replace_confirmed_entry(chapter_id, confirmed_entry)
                    previous_draft_id = str(existing_confirmed.get("source_draft_id") or "")
                    if previous_draft_id and previous_draft_id != draft_id:
                        self._clear_draft_commit_status(
                            previous_draft_id,
                            replaced_at=committed_at,
                            replacement_draft_id=draft_id,
                            chapter_id=chapter_id,
                        )
                else:
                    self._append_confirmed_entry(confirmed_entry)
                self._update_draft_status(draft_id, status="committed", committed_at=committed_at, chapter_id=chapter_id)
                self._append_commit_log(
                    {
                        "commit_id": f"{committed_at}_{uuid4().hex[:12]}",
                        "timestamp": committed_at,
                        "draft_id": draft_id,
                        "chapter_id": chapter_id,
                        "status": "replaced" if existing_confirmed is not None else "committed",
                        "provider": artifact["provider"]["provider"],
                        "model": artifact["provider"]["model"],
                        "usage": artifact["provider"]["usage"],
                        "checkpoint_id": checkpoint.get("checkpoint_id"),
                        "commit_gate": commit_gate,
                        "replacement": artifact["replacement"],
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
                if chapter_id and not isinstance(exc, DraftCommitGateError):
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

    def update_draft_content(self, draft_id: str, *, text: str) -> dict[str, Any]:
        self.store.initialize()
        with self.store.lock():
            draft_entry = self._draft_index_entry(draft_id)
            draft = self.read_draft(draft_id)
            updated_at = utc_stamp()
            draft["content"] = str(text or "")
            draft["edited_at"] = updated_at
            self.store.write_json(str(draft_entry["path"]), draft)
            self._update_draft_index_entry(
                draft_id,
                {
                    "edited_at": updated_at,
                    "content_chars": len(str(text or "")),
                },
            )
            synced_confirmed = self._sync_confirmed_content_from_draft(draft_id, str(text or ""), updated_at)
            return {
                "draft_id": draft_id,
                "chapter_id": str(draft.get("chapter_id") or ""),
                "edited_at": updated_at,
                "content_chars": len(str(text or "")),
                "synced_confirmed_chapter": synced_confirmed,
            }

    def next_chapter_draft_version(self, chapter_id: str) -> int:
        validate_chapter_id(chapter_id)
        versions: list[int] = []
        for item in self.list_drafts():
            if item.get("chapter_id") != chapter_id:
                continue
            version = safe_positive_int(item.get("version"))
            if version is not None:
                versions.append(version)
                continue
            label = str(item.get("version_label") or "")
            match = re.fullmatch(r"ver(\d+)", label)
            if match:
                versions.append(int(match.group(1)))
        return max(versions, default=0) + 1

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

    def _update_draft_index_entry(self, draft_id: str, updates: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        drafts = index.get("drafts") if isinstance(index, dict) and isinstance(index.get("drafts"), list) else []
        updated: list[dict[str, Any]] = []
        for item in drafts:
            if isinstance(item, dict) and item.get("draft_id") == draft_id:
                item = {**item, **updates}
            if isinstance(item, dict):
                updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "drafts": updated})

    def _update_draft_status(self, draft_id: str, *, status: str, committed_at: str, chapter_id: str) -> None:
        draft_entry = self._draft_index_entry(draft_id)
        draft = self.read_draft(draft_id)
        draft["status"] = status
        draft["committed_at"] = committed_at
        draft["committed_chapter_id"] = chapter_id
        self.store.write_json(str(draft_entry["path"]), draft)
        self._update_draft_index_entry(
            draft_id,
            {"status": status, "committed_at": committed_at, "committed_chapter_id": chapter_id},
        )

    def _clear_draft_commit_status(
        self,
        draft_id: str,
        *,
        replaced_at: str,
        replacement_draft_id: str,
        chapter_id: str,
    ) -> None:
        try:
            draft_entry = self._draft_index_entry(draft_id)
            draft = self.read_draft(draft_id)
        except Exception:
            return
        draft["status"] = "draft"
        draft.pop("committed_at", None)
        draft.pop("committed_chapter_id", None)
        draft["confirmation_replaced_by"] = {
            "draft_id": replacement_draft_id,
            "chapter_id": chapter_id,
            "replaced_at": replaced_at,
        }
        self.store.write_json(str(draft_entry["path"]), draft)
        self._update_draft_index_entry(
            draft_id,
            {
                "status": "draft",
                "committed_at": "",
                "committed_chapter_id": "",
                "confirmation_replaced_by": replacement_draft_id,
            },
        )

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

    def _replace_confirmed_entry(self, chapter_id: str, entry: dict[str, Any]) -> None:
        chapters: list[dict[str, Any]] = []
        replaced = False
        for item in self._read_confirmed_index():
            if item.get("chapter_id") == chapter_id:
                chapters.append(entry)
                replaced = True
                continue
            chapters.append(item)
        if not replaced:
            chapters.append(entry)
        self.store.write_json(self.confirmed_index_path, {"schema_version": 1, "chapters": chapters})

    def _sync_confirmed_content_from_draft(self, draft_id: str, text: str, updated_at: str) -> str:
        synced_chapter_id = ""
        updated_index: list[dict[str, Any]] = []
        for item in self._read_confirmed_index():
            if item.get("source_draft_id") == draft_id:
                chapter_id = str(item.get("chapter_id") or "")
                path = item.get("path")
                if isinstance(path, str) and chapter_id:
                    chapter = self.store.read_json(path, default=None)
                    if isinstance(chapter, dict):
                        chapter["content"] = text
                        chapter["edited_at"] = updated_at
                        chapter["edit_source"] = "source_draft_editor"
                        self.store.write_json(path, chapter)
                        item = {**item, "edited_at": updated_at}
                        synced_chapter_id = chapter_id
            if isinstance(item, dict):
                updated_index.append(item)
        if synced_chapter_id:
            self.store.write_json(self.confirmed_index_path, {"schema_version": 1, "chapters": updated_index})
        return synced_chapter_id

    def _append_commit_log(self, entry: dict[str, Any]) -> None:
        log = self.read_commit_log()
        commits = log.get("commits") if isinstance(log.get("commits"), list) else []
        commits.append(entry)
        self.store.write_json(self.commit_log_path, {"schema_version": 1, "commits": commits})

    def _delete_related_index_entries(
        self,
        *,
        index_path: Path,
        list_key: str,
        chapter_id: str,
        draft_ids: set[str],
        retained_draft_ids: set[str],
        retired_paths: list[str],
    ) -> list[str]:
        index = self.store.read_json(index_path, default={"schema_version": 1, list_key: []})
        items = index.get(list_key) if isinstance(index, dict) and isinstance(index.get(list_key), list) else []
        kept: list[dict[str, Any]] = []
        removed_ids: list[str] = []
        id_key = "review_id" if list_key == "reviews" else "revision_request_id"
        for item in items:
            if not isinstance(item, dict):
                continue
            item_draft_id = str(item.get("draft_id") or "")
            item_chapter_id = str(item.get("chapter_id") or "")
            should_remove = item_draft_id in draft_ids or (
                item_chapter_id == chapter_id and item_draft_id not in retained_draft_ids
            )
            if not should_remove:
                kept.append(item)
                continue
            removed_ids.append(str(item.get(id_key) or ""))
            retired = retire_indexed_artifact(self.store, item.get("path"))
            if retired:
                retired_paths.append(retired)
        self.store.write_json(index_path, {"schema_version": 1, list_key: kept})
        return [item for item in removed_ids if item]

    def _write_context_generation_summary(self, draft_id: str, render: dict[str, Any], *, mode: str) -> None:
        draft_entry = self._draft_index_entry(draft_id)
        draft = self.read_draft(draft_id)
        package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
        sections = package.get("sections") if isinstance(package.get("sections"), list) else []
        skipped = package.get("skipped") if isinstance(package.get("skipped"), list) else []
        summary = {
            "mode": mode,
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
    prompt_message = next(
        (
            item
            for item in render.get("rendered_messages", [])
            if isinstance(item, dict) and item.get("label") == "draft_prompt"
        ),
        {},
    )
    prompt = str(prompt_message.get("content") or "").strip()
    target_message = next(
        (
            item
            for item in render.get("rendered_messages", [])
            if isinstance(item, dict) and item.get("label") == "target_chapter"
        ),
        {},
    )
    target_chapter = str(target_message.get("content") or "").strip()
    lines: list[str] = []
    context_text = render_context_materials(sections)
    if context_text:
        lines.append("【创作资料】")
        lines.append(context_text)
    if target_chapter:
        if lines:
            lines.append("")
        lines.append("【目标章节】")
        lines.append(target_chapter)
    if prompt:
        if lines:
            lines.append("")
        lines.append("【用户本次要求】")
        lines.append(prompt)
    if not lines:
        lines.append("【用户本次要求】")
        lines.append(prompt)
    return "\n".join(lines).strip()


def render_context_materials(sections: list[object]) -> str:
    stable, volatile = partition_context_sections(sections)
    lines: list[str] = []
    for group in [*grouped_context_sections(stable), *grouped_context_sections(volatile)]:
        if lines:
            lines.append("")
        lines.append(f"【{group['label']}】")
        for item in group["items"]:
            title = str(item.get("title") or item.get("source_id") or "").strip()
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            if title:
                lines.append(f"{title}:")
            lines.append(text)
    return "\n".join(lines).strip()


def partition_context_sections(sections: list[object]) -> tuple[list[object], list[object]]:
    stable: list[object] = []
    volatile: list[object] = []
    for item in sections:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type") or "")
        category_id = str(item.get("category_id") or "")
        if source_type in {"memory_bank", "recent_confirmed_chapter"} or category_id in {
            "chapter_plan",
            "recent_chapters",
        }:
            volatile.append(item)
        else:
            stable.append(item)
    return stable, volatile


def grouped_context_sections(sections: list[object]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in sections:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        label = str(item.get("section_label") or item.get("category_id") or "补充资料")
        order = safe_group_order(item.get("section_order"))
        group = groups.setdefault(label, {"label": label, "order": order, "items": []})
        group["order"] = min(int(group["order"]), order)
        group["items"].append(item)
    return sorted(groups.values(), key=lambda value: (int(value["order"]), str(value["label"])))


def safe_group_order(value: object) -> int:
    if isinstance(value, bool):
        return 999
    if isinstance(value, int):
        return value
    return 999


def sanitize_provider_draft_text(text: str) -> dict[str, Any]:
    original = str(text or "")
    without_blocks, block_count = REASONING_BLOCK_PATTERN.subn("", original)
    without_tags, tag_count = REASONING_TAG_PATTERN.subn("", without_blocks)
    content = without_tags.strip()
    return {
        "content": content,
        "summary": {
            "reasoning_markup_detected": block_count > 0 or tag_count > 0,
            "reasoning_blocks_removed": block_count,
            "reasoning_tags_removed": tag_count,
            "chars_removed": max(len(original) - len(content), 0),
        },
    }


def stream_sanitizer_callback(
    callback: Callable[[str], None] | None,
    reasoning_callback: Callable[[str], None] | None = None,
) -> Callable[[str], None] | None:
    if callback is None:
        return None
    sanitizer = StreamingReasoningSanitizer(reasoning_callback=reasoning_callback)

    def wrapped(chunk: str) -> None:
        safe_chunk = sanitizer.feed(str(chunk or ""))
        if safe_chunk:
            callback(safe_chunk)

    return wrapped


class StreamingReasoningSanitizer:
    def __init__(self, *, reasoning_callback: Callable[[str], None] | None = None) -> None:
        self.buffer = ""
        self.inside_reasoning = False
        self.reasoning_callback = reasoning_callback

    def emit_reasoning(self, text: str) -> None:
        if text and self.reasoning_callback is not None:
            self.reasoning_callback(text)

    def feed(self, chunk: str) -> str:
        text = self.buffer + chunk
        self.buffer = ""
        output: list[str] = []
        index = 0
        while index < len(text):
            lower = text.lower()
            if self.inside_reasoning:
                end = lower.find("</think", index)
                if end == -1:
                    tail = text[index:]
                    keep = partial_reasoning_close_prefix_len(tail)
                    if keep:
                        self.emit_reasoning(tail[:-keep])
                        self.buffer = tail[-keep:]
                    else:
                        self.emit_reasoning(tail)
                    return "".join(output)
                close = text.find(">", end)
                if close == -1:
                    self.emit_reasoning(text[index:end])
                    self.buffer = text[end:]
                    return "".join(output)
                self.emit_reasoning(text[index : close + 1])
                self.inside_reasoning = False
                index = close + 1
                continue
            start = lower.find("<think", index)
            close_start = lower.find("</think", index)
            candidates = [position for position in (start, close_start) if position != -1]
            if not candidates:
                tail = text[index:]
                keep = partial_reasoning_tag_prefix_len(tail)
                if keep:
                    output.append(tail[:-keep])
                    self.buffer = tail[-keep:]
                else:
                    output.append(tail)
                return "".join(output)
            tag_start = min(candidates)
            output.append(text[index:tag_start])
            tag_close = text.find(">", tag_start)
            if tag_close == -1:
                self.buffer = text[tag_start:]
                return "".join(output)
            self.emit_reasoning(text[tag_start : tag_close + 1])
            if tag_start == start:
                self.inside_reasoning = True
            index = tag_close + 1
        return "".join(output)


def partial_reasoning_tag_prefix_len(value: str) -> int:
    lower = value.lower()
    prefixes = ("<think", "</think")
    max_length = max(len(item) for item in prefixes)
    for length in range(min(len(lower), max_length), 0, -1):
        suffix = lower[-length:]
        if any(prefix.startswith(suffix) for prefix in prefixes):
            return length
    return 0


def partial_reasoning_close_prefix_len(value: str) -> int:
    lower = value.lower()
    prefix = "</think"
    for length in range(min(len(lower), len(prefix)), 0, -1):
        if prefix.startswith(lower[-length:]):
            return length
    return 0


def safe_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def retire_indexed_artifact(store: ProjectStore, path_value: object) -> str:
    if not isinstance(path_value, str) or not path_value.strip():
        return ""
    target = store._resolve_owned_path(path_value)
    if not target.exists():
        return ""
    return str(retire_path(target))


def retire_orphan_chapter_artifacts(
    store: ProjectStore,
    directory: Path,
    pattern: str,
    retained_draft_ids: set[str],
) -> list[str]:
    if not directory.exists():
        return []
    retired: list[str] = []
    for path in sorted(directory.glob(pattern)):
        target = store._resolve_owned_path(path)
        if not target.is_file():
            continue
        if any(draft_id and draft_id in target.name for draft_id in retained_draft_ids):
            continue
        retired.append(str(retire_path(target)))
    return retired


def validate_chapter_id(chapter_id: str) -> None:
    value = chapter_id.strip()
    if not value or value in {".", ".."}:
        raise DraftGenerationError("chapter_id cannot be empty, '.' or '..'.")
    if any(separator in value for separator in ("/", "\\", ":", " ")):
        raise DraftGenerationError(f"Unsafe chapter_id: {chapter_id!r}")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise DraftGenerationError(f"Unsafe chapter_id: {chapter_id!r}")


def accepted_review_commit_gate(store: ProjectStore, draft: dict[str, Any]) -> dict[str, Any]:
    draft_id = str(draft.get("draft_id") or "")
    chapter_id = str(draft.get("chapter_id") or "")
    index = store.read_json(store.data_dir / "reviews_index.json", default={"reviews": []})
    reviews = index.get("reviews") if isinstance(index, dict) and isinstance(index.get("reviews"), list) else []
    for entry in reviews:
        if not isinstance(entry, dict) or str(entry.get("draft_id") or "") != draft_id:
            continue
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        review = store.read_json(path, default=None)
        if not isinstance(review, dict):
            continue
        if str(review.get("draft_id") or "") != draft_id or str(review.get("chapter_id") or "") != chapter_id:
            continue
        decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
        if str(decision.get("status") or "") != "accepted":
            continue
        reason_code = str(decision.get("reason_code") or "")
        if reason_code in NON_COMMITTABLE_ACCEPTED_REVIEW_REASON_CODES:
            raise DraftCommitGateError(f"Accepted review is marked non-committable: {reason_code}")
        gate: dict[str, Any] = {
            "required": True,
            "allowed": True,
            "review_id": str(review.get("review_id") or entry.get("review_id") or ""),
            "decision": "accepted",
            "decided_at": str(decision.get("decided_at") or ""),
            "reason_code": reason_code,
        }
        manual_rewrite = draft.get("manual_rewrite") if isinstance(draft.get("manual_rewrite"), dict) else {}
        if str(manual_rewrite.get("mode") or "") == "manual_rewrite_draft_candidate":
            request_summary = review.get("request_summary") if isinstance(review.get("request_summary"), dict) else {}
            review_gate = (
                request_summary.get("manual_rewrite_review_gate")
                if isinstance(request_summary.get("manual_rewrite_review_gate"), dict)
                else {}
            )
            if review_gate.get("allowed") is not True or str(review_gate.get("matched_gate") or "") not in {
                "selected_for_review_comparison",
                "pending_review_handoff",
            }:
                raise DraftCommitGateError("Manual rewrite draft commit requires a guarded accepted review.")
            gate["manual_rewrite_review_gate"] = {
                "matched_gate": str(review_gate.get("matched_gate") or ""),
                "comparison_id": str(review_gate.get("comparison_id") or ""),
                "handoff_id": str(review_gate.get("handoff_id") or ""),
            }
        return gate
    raise DraftCommitGateError("Draft commit requires an accepted review for the same draft.")


def confirmed_replacement_summary(existing_confirmed: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(existing_confirmed, dict) or not existing_confirmed:
        return {"replaced": False}
    return {
        "replaced": True,
        "previous_source_draft_id": str(existing_confirmed.get("source_draft_id") or ""),
        "previous_source_draft_version_label": str(existing_confirmed.get("source_draft_version_label") or ""),
        "previous_committed_at": str(existing_confirmed.get("committed_at") or ""),
    }
