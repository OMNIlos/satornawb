# Satorna WB

Public source snapshot of the Satorna marketplace operations platform.

## Structure

- `frontend/` — Vite, React and TypeScript application with Vercel API routes.
- `backend/` — FastAPI modular monolith, Alembic migrations and tests.
- `SATORNA_DELEGATION_PROMPTS/` — standalone task prompts.
- `SATORNA_ARCHITECTURE_HANDOFF.md` — authoritative architecture and rollout state.
- `SATORNA_SPEC_AUDIT.md` — specification audit.

## Production snapshot

Published on 2026-09-08:

- backend application revision: `b96e602`;
- backend documentation revision: `e5c0b5b`;
- production image: `sha256:0aad3379406afd344b1ede23859350752f40efe9a2e8d19a988f8431f4040fa1`;
- Alembic head: `20260905_0060`;
- the frontend tree is unchanged from the preceding `main` snapshot.

Secrets, environment files, runtime state, caches and production backups are not
part of this repository.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Quality checks:

```bash
cd frontend
npm run typecheck
npm run test
npm run build
```

## Frontend deployment

The production deployment is managed by Vercel from the `frontend/` directory.

Expected Vercel settings:

- Framework preset: Vite
- Root directory: `frontend`
- Install command: `npm install`
- Build command: `npm run build`
- Output directory: `dist`
