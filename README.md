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

Production runs on the Beget server at `https://comcookie.store`: nginx
serves the built `frontend/dist` and proxies `/api/*` on the same host to the
backend container, so the browser talks to a single origin.

```bash
deploy/frontend-release.sh                     # build this commit and make it live
deploy/frontend-release.sh --list              # releases on the server, * marks the live one
deploy/frontend-release.sh --switch <release>  # make an uploaded release live (rollback)
```

- Build flags: `deploy/frontend-production.env`.
- nginx site: `deploy/nginx/comcookie.store.conf`.
- The script needs Node 22.12+, rsync and the `satorna-api` SSH alias.

The former Vercel deployment (`satorna-wb.vercel.app`) is frozen and receives no
new releases; `frontend/vercel.json` and `frontend/api/` only matter to it.
