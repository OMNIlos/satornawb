# First manual Review draft — bounded backend handoff

ROOT froze `mode="manual"` for first human text on 2026-09-10. The existing `review.draft.publish.v1` command now accepts this additive `review-generation-v1` mode without `previousDraftId`. Preparation requires an existing source, selected policy, and no draft/workflow head. Command validation requires both expected versions zero; repository publication independently requires no current head. Manual edit semantics are unchanged. Policy template/model labels remain captured policy metadata and never assert AI generation.

No service authority path was added: existing `execute_local_review` revalidates current session/membership/permission/exact account through physical commit, including command replay. Existing source/policy checks, immutable audit, receipt, and CAS remain in force. Missing policy fails closed. No provider, send, bootstrap, frontend, DDL, runtime configuration, or JSON fixture changes.

## Required T1 SQL amendment (not implemented here)

- Generation codec/check accepts literal `manual` alongside existing `fake`/`manual_edit`.
- Manual generation keyset equals fake keyset: `previousDraftId` forbidden; storage `previous_draft_id` NULL.
- Manual draft storage revision must equal 1. First publication command requires expected head/draft revision both 0; workflow publication must reject an existing head. Existing immutable history, receipt and audit checks remain.
- SQL canonical encoder must emit the following UTF-8 bytes exactly (no trailing newline), SHA256 `8719f302e913cebc2ac3d135ce04d31f0408611588b17fa49c9457f9bc152443`:

```json
{"actorMembershipId":3,"completedAt":"2026-09-09T12:00:01.654321Z","generationId":"10000000-0000-4000-8000-000000000005","mode":"manual","modelVersion":"fake-v1","policyChecksum":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","policyId":"10000000-0000-4000-8000-000000000001","policyVersion":9223372036854775808,"schemaVersion":"review-generation-v1","sourceChecksum":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","sourceObservationId":"10000000-0000-4000-8000-000000000006","startedAt":"2026-09-09T12:00:00.123456Z","templateVersion":"manual-v1"}
```

This vector is `tests.test_review_manual_draft.manual_command()['input']['generation']`, derived from the existing synthetic golden command, changing mode only. Its fake-v1 label is deliberately preserved metadata, not a producer claim. Invalid vectors: add any previousDraftId; command versions `(1,1)`, `(4,2)`, `(0,1)`, `(1,0)`; empty/whitespace/lone-surrogate text; mode `manual` with revision greater than 1 or a predecessor in persisted storage.

## Evidence and remaining dependencies

RED: `/tmp/satorna-backend311-20260909/bin/python -m pytest tests/test_review_manual_draft.py -q` → 2 failed/14 passed, failures caused by missing manual mode.

GREEN: same runtime, `-m pytest tests/test_review_manual_draft.py tests/test_review_local_command_payload.py tests/test_review_storage_payloads.py -q` → 135 passed in 0.13s. Existing fake/manual_edit golden checks passed. Ruff with backend config passed all six changed Python files. `git diff --check` passed.

New PostgreSQL acceptance file `tests/test_review_manual_draft_storage.py` contains five cases: first draft/replay/competing-first/manual-edit/approval lifecycle; session, permission and account-scope revocation on replay; source-change conflict. These cases are NOT RUN: T1 owns heavy PG slot and schema amendment. No full-suite or database acceptance claim. ROOT/T1 must apply amendment and run these with the allocated isolated PG slot; existing policy epoch, binding, transaction rollback and publication race regressions remain relevant unchanged coverage.

Self critic pass: principal risks are schema/codec disagreement and mislabeling policy metadata as AI provenance. SQL dependency is explicit, and UI owner must label `Ручной черновик`, retain exact command on transport retry, and use manual_edit after first draft. The required local preflight-critic SKILL.md was absent (no match under skills); a separate manual review checked the diff and verification limits. No full Reviews completion claim. ROOT owns shared project memory update to avoid concurrent memory edits.
