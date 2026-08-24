# Vella WB 19.05 backend contract package

Portable FastAPI/Pydantic reference package for the 19.05 Vella runtime boundary.

This is not a production backend. It is a copy-ready package for the future
FastAPI repo so Sprint A can return contract-shaped blocked/partial states
before real WB sources are confirmed.

## What it covers

- P&L, Ads, RNP and ABC report response models.
- SPP price guard model and blocked default stub.
- AI review approval guard model.
- Source/blocker registry seed for 19.05 blockers.
- FastAPI router with read-only stub endpoints.
- Negative tests for the invariants that must not regress.

## Run checks

From the project root:

```bash
uvx --with pydantic --with fastapi --with httpx --with pytest pytest backend_contracts/tests
python3 -m py_compile backend_contracts/vella_wb_19_05/*.py
```

## Integration default

Until WB sources are confirmed, backend must return `partial`, `blocked` or
`unknown` states with explicit blocker IDs. It must not turn campaign-only ads,
unconfirmed P&L costs, unknown SPP or risky review drafts into final/ready states.
