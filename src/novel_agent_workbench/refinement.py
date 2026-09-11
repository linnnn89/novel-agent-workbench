"""AI review refinement, from an unchanged source draft to a new candidate."""
from __future__ import annotations

from typing import Any, Callable

from .chapters import ChapterWorkflowService
from .context_assembler import ContextAssemblerService
from .drafts import DraftGenerationService, render_shared_context_block, sanitize_provider_draft_text, stream_sanitizer_callback
from .providers import ProviderRequest, generate_with_provider, get_effective_model_role_config, provider_request_role_or_writer_fallback
from .reviews import DraftReviewService, is_ai_review, ai_review_matches_draft, render_context_stats, draft_content_fingerprint, finish_reason_truncated
from .storage import ProjectStore
from .token_budget import capacity_check, estimate_input_tokens


AI_REFINEMENT_SYSTEM_PROMPT = (
    "你是一名专业小说改稿编辑。当前任务不是续写新章节，而是按 AI 审稿意见改写待改原文。"
    "AI 审稿意见是本次改稿的主要约束，必须逐条落实其中明确指出的问题。"
    "待改原文只供对照，禁止整章原样输出。"
    "保留既有事实、人物关系和情节因果；被审稿点名的段落、对白和描写必须改写。"
    "若审稿意见与已给定上下文或前文事实冲突，用正文方式化解，不得无视审稿。"
    "只输出修订后的小说正文，不输出说明、分析或 <think>。"
)



class DraftRefinementService:
    def __init__(self, store: ProjectStore, *, generation_settings: dict[str, Any]):
        self.store = store
        self.generation_settings = generation_settings

    def refine_draft(
        self,
        draft_id: str,
        *,
        review_id: str = "",
        instruction: str = "",
        max_context_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        repetition_penalty: float | None = None,
        stream: bool | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        store = self.store
        draft_service = DraftGenerationService(store)
        review_service = DraftReviewService(store)
        draft = draft_service.read_draft(draft_id)
        review = review_service.read_review(review_id) if review_id else review_service.find_ai_review_for_draft(draft_id)
        if not isinstance(review, dict) or not review:
            raise RuntimeError("Current draft has no AI review; local/manual review cannot drive AI refinement.")
        if str(review.get("draft_id") or "") != draft_id or not is_ai_review(review):
            raise RuntimeError("Only an AI review for this exact draft can drive AI refinement.")
        if not ai_review_matches_draft(review, draft):
            raise RuntimeError("审稿已过期、不完整或缺少正文版本校验，请对当前正文重新进行 AI 审稿。")
        chapter_id = str(draft.get("chapter_id") or "")
        title = str(draft.get("title") or "")
        settings = self.generation_settings
        if max_tokens is None:
            max_tokens = int(settings.get("sampling", {}).get("max_tokens") or 16)
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        system_prompt = ai_refinement_system_prompt(str(prompting.get("system_prompt") or ""))
        task_prompt = ai_refinement_task_prompt(
            chapter_id=chapter_id,
            title=title,
            instruction=instruction,
        )
        render = ContextAssemblerService(store).prompt_render_dry_run(
            prompt=task_prompt,
            system_prompt=system_prompt,
            max_context_tokens=max_context_tokens,
            chapter_id=chapter_id,
            include_prompt_text=True,
            include_context_text=True,
        ).to_dict()
        provider_prompt = render_ai_refinement_prompt(render, draft=draft, review=review, instruction=instruction)
        request_role = provider_request_role_or_writer_fallback(
            store,
            "reviser",
            feature_id="ai_refinement",
        )
        capacity = refinement_capacity_check(
            store.read_config(), provider_prompt, system_prompt,
            input_limit=max_context_tokens, max_tokens=max_tokens, role=request_role,
            model=get_effective_model_role_config(store, request_role, feature_id="ai_refinement").model,
        )
        safe_stream_callback = stream_sanitizer_callback(stream_callback, reasoning_callback)
        try:
            response = generate_with_provider(
                store,
                ProviderRequest(
                    role=request_role,
                    feature_id="ai_refinement",
                    prompt=provider_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    min_p=min_p,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                    repetition_penalty=repetition_penalty,
                    stream=stream,
                    stream_callback=safe_stream_callback,
                    reasoning_callback=reasoning_callback,
                    metadata={
                        "ai_review_refinement": True,
                        "chapter_id": chapter_id,
                        "draft_id": draft_id,
                        "review_id": str(review.get("review_id") or ""),
                        "context_aware_refinement": True,
                        "input_token_limit": capacity["configured_input_limit"],
                    },
                ),
            )
        except Exception as exc:
            ChapterWorkflowService(store).record_error(
                chapter_id,
                title=title,
                stage="ai_review_refine_draft",
                error_type=getattr(exc, "error_type", exc.__class__.__name__),
                message=str(exc),
            )
            raise
        context_stats = render_context_stats(render)
        source_sanitized = sanitize_provider_draft_text(str(draft.get("content") or ""))
        if not sanitize_provider_draft_text(response.text)["content"].strip():
            raise RuntimeError("精修未返回可用正文，未创建新草稿。")
        result = draft_service.save_provider_draft_version(
            chapter_id=chapter_id,
            title=title,
            content=response.text,
            provider_role="reviser",
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            request_summary={
                "prompt_chars": len(provider_prompt),
                "system_prompt_chars": len(system_prompt),
                "review_chars": len(str(review.get("comment") or "")),
                "source_draft_chars": len(str(draft.get("content") or "")),
                "provider_source_draft_chars": len(source_sanitized["content"]),
                "provider_request_role": request_role,
                "logical_role": "reviser",
                "metadata_keys": [
                    "ai_review_refinement",
                    "chapter_id",
                    "context_aware_refinement",
                    "draft_id",
                    "review_id",
                ],
                "source_draft_sanitizer": source_sanitized["summary"],
                **context_stats,
                **capacity,
            },
            artifact_metadata={
                "output_incomplete": finish_reason_truncated(response.finish_reason),
                "revision": {
                    "mode": "ai_review_refinement",
                    "source_draft_id": draft_id,
                    "source_content_sha256": draft_content_fingerprint(draft.get("content")),
                    "source_review_id": str(review.get("review_id") or ""),
                    "source_review_type": str(review.get("review_type") or ""),
                    "source_draft_status": str(draft.get("status") or ""),
                    "instruction": str(instruction or "").strip(),
                }
            },
        )
        return {
            **result.to_dict(),
            "output_incomplete": finish_reason_truncated(response.finish_reason),
        }



def estimate_refinement_input_tokens(system_prompt: str, prompt: str) -> int:
    return estimate_input_tokens(system_prompt, prompt)


def refinement_capacity_check(
    config: dict[str, Any], prompt: str, system_prompt: str, *,
    input_limit: int | None, max_tokens: int | None, role: str, model: str = "deepseek-v4",
) -> dict[str, Any]:
    return capacity_check(config, prompt, system_prompt, feature_id="ai_refinement", role=role,
                          input_limit=input_limit, max_tokens=max_tokens, model=model)


def ai_refinement_system_prompt(project_system_prompt: str = "") -> str:
    project_prompt = str(project_system_prompt or "").strip()
    base_prompt = AI_REFINEMENT_SYSTEM_PROMPT.strip()
    if not project_prompt or project_prompt == base_prompt:
        return base_prompt
    return "\n\n".join(
        [
            base_prompt,
            "【项目通用写作规则】",
            project_prompt,
            "以上通用规则不得覆盖本次 AI 审稿意见；若存在冲突，优先保持既有事实连续性并落实审稿指出的问题。",
        ]
    )


def ai_refinement_task_prompt(*, chapter_id: str, title: str = "", instruction: str = "") -> str:
    heading = f"{chapter_id}"
    if title:
        heading = f"{heading}（{title}）"
    user_instruction = str(instruction or "").strip()
    lines = [
        f"请根据 AI 审稿意见精修当前章节：{heading}。",
        "必须优先解决审稿指出的问题；待改原文禁止整章原样输出。",
        "保留主线事实和人物动机，但必须改写被点名的段落和措辞。",
        "输出必须是修订后的小说正文，不要写分析过程、修改说明、免责声明或 <think>。",
    ]
    if user_instruction:
        lines.append(f"额外精修要求：{user_instruction}")
    return "\n".join(lines)


def render_ai_refinement_prompt(
    render: dict[str, Any],
    *,
    draft: dict[str, Any],
    review: dict[str, Any],
    instruction: str = "",
) -> str:
    package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
    sections = package.get("sections") if isinstance(package.get("sections"), list) else []
    context_block = render_shared_context_block(sections)
    draft_text = sanitize_provider_draft_text(str(draft.get("content") or ""))["content"]
    review_text = str(review.get("comment") or "").strip()
    chapter_id = str(draft.get("chapter_id") or "")
    title = str(draft.get("title") or "")
    version_label = str(draft.get("version_label") or "")
    lines: list[str] = []
    if context_block:
        lines.extend([context_block, ""])
    lines.extend(
        [
            "【目标章节】",
            f"章节 ID：{chapter_id}",
            f"标题：{title or chapter_id}",
            f"源草稿版本：{version_label or '-'}",
            "",
            "【待改原文（禁止原样整章输出）】",
            "下面是需要改写的原文，只供对照。不要把它整章复制后当作完成。",
            draft_text or "（空草稿）",
            "",
            "【精修任务】",
            "根据后面的审稿意见，把待改原文改成一个新的修订版。",
            "保留既有事实、人物关系和情节因果，不要另起一条新剧情。",
            "被审稿点名的段落、对白、节奏和感官描写必须改写，不能只做个别用词替换。",
            "",
            "【必须落实的 AI 审稿意见】",
            review_text or "（无审稿意见）",
        ]
    )
    if str(instruction or "").strip():
        lines.extend(["", "【用户额外要求】", str(instruction or "").strip()])
    lines.extend(
        [
            "",
            "【输出要求】",
            "直接输出精修后的完整章节正文。",
            "正文必须能看出审稿意见已被落实，且不得与待改原文整章逐字相同。",
            "不要列出修改清单，不要输出审稿、分析、提纲、说明、免责声明或 <think>。",
        ]
    )
    return "\n".join(lines).strip()
