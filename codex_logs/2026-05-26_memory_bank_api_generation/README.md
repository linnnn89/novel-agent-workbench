# Memory Bank API Generation

Date: 2026-05-26, Asia/Shanghai.

## Operation

Added an explicit desktop Memory Bank action that sends the current Memory Bank body plus checked confirmed chapters to the configured writer Provider and fills the returned text into the editor.

The generated text is not auto-saved. The user must inspect it and click `保存记忆正文`.

## Prompt And Request Shape

- Provider role: `writer`, using the normal project/global runtime Provider configuration.
- Messages: one system message defining the Memory Bank editor role and one user message containing the current Memory Bank plus delimited confirmed chapter blocks.
- Sampling defaults: `temperature=0.2`, `top_p=0.9`, `stream=false`, and `max_tokens` set above the visible target budget so the OpenAI-compatible adapter does not fall back to its short default.
- Metadata is local request metadata only; it records `memory_bank_generation`, selected chapter ids, chapter count, target token budget, and existing memory length.

## Files Changed

- `src/novel_agent_workbench/memory_bank.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/desktop_app.py`
- `src/novel_agent_workbench/__init__.py`
- `tests/test_memory_bank_api_generation.py`
- `codex_logs/README.md`
- `codex_logs/2026-05-26_memory_bank_api_generation/README.md`

## Safety Boundaries

- The API call is only triggered by the explicit `发送给AI生成记忆` button.
- The generated Memory Bank body is placed in the text editor only; it is not persisted until the existing save button is clicked.
- Provider call logs keep prompt/chapter text out of persistent logs.
- No RAG, export, confirmed chapter, draft, or Memory Bank save side effects are performed by generation itself.

## Verification

```powershell
py -3.13 -m unittest discover -s tests
py -3.13 -m compileall src tests
```

## Next Step

Manually test the packaged desktop app against a real configured writer Provider and confirm the generated Memory Bank body is acceptable before saving.
