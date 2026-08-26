# Important Open Issues

Date: 2026-05-18, Asia/Shanghai.

This file tracks architectural problems that must stay visible across context compression and future coding sessions.

## OI-001 Memory Bank Priority Is Local Logic, Not LLM API Logic

Status: open, high priority.

### Problem

Current LLM APIs generally accept message arrays and generation parameters. They do not provide a portable native field such as:

```text
memory_priority
memory_weight
context_importance
```

Therefore Memory Bank priority cannot be delegated to the Provider API. It must be implemented locally before each Provider call.

### Current Implementation State

Implemented today:

```text
formal_context_policy.priority_order
formal_context_plans categories
category priority
category memory_weight
world_book overlap policy for world_building
```

Not implemented yet:

```text
actual Memory Bank item extraction
actual Memory Bank item ranking
actual context assembly into ProviderRequest messages
actual token-budget truncation with real tokenizer
deduplication between world book and Memory Bank
```

### Required Future Design

Before any real long-form generation workflow depends on Memory Bank, implement and test a local Context Assembler:

```text
1. collect candidate context items from confirmed chapters, Memory Bank, world book, planning library, and formal context plans
2. score by category priority, memory_weight, recency, importance, and source reliability
3. deduplicate world book and Memory Bank overlap
4. estimate or tokenize against the role/model budget
5. select and order items locally
6. render selected items into the final ProviderRequest messages
```

### Current Risk

If this is skipped, the system may:

- waste tokens by repeating world-building facts in both world book and Memory Bank,
- include lower-priority context while dropping higher-priority context,
- create prompt bloat that real Provider APIs cannot fix automatically,
- make debugging generation quality difficult because the prompt assembly decision is invisible.

### Immediate Mitigation

MVP-8 adds a metadata-only Context Assembler dry-run command that shows candidate order, estimated token budget, selected/skipped status, and world-book overlap recommendations without calling Providers or returning chapter text.

Remaining after MVP-8:

```text
real tokenizer
actual Memory Bank extraction
deduplication against real world book entries
final ProviderRequest message rendering
```

## OI-002 Final Real Provider Safety Disable Reminder

Status: open, high priority.

### Problem

The current Chutes writer path intentionally keeps the real Provider adapter/generation state safety-disabled outside explicit authorized execution windows. This is correct for engineering validation and upload readiness, but it must not be forgotten when the project reaches final production-use preparation.

### Required Final Reminder

Before the final real production workflow is used, explicitly remind the operator to decide whether to close the safety-disabled state for the real Provider path.

The reminder must include:

```text
1. confirm the intended Provider/model/key reference
2. close or keep the safety-disabled state by explicit operator decision
3. run Provider smoke test after any change
4. run project-health
5. run prepublish-check
```

### Boundary

Do not automatically close the safety-disabled state. Do not call the Provider, rotate keys, clear keys, or change runtime Provider config unless the operator explicitly authorizes that specific step.
