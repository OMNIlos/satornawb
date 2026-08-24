# Ogni SaS


Private product repository for the Ogni marketplace operations SaaS


The current deployable application lives in `frontend/`. Project documentation,
approved requirements, research, and working notes are kept in the repository so
implementation decisions stay close to the code.
## Structure

- `frontend/` - Vite + React + TypeScript application and Vercel API routes.
- `docs/` - architecture notes, design system docs, module descriptions, and API contracts.
- `ТЗ/` - approved technical requirements for WB and Avito modules.
- `research/` - marketplace/API/competitor research used for product decisions.
- `Встречи/` - meeting notes and derived text materials.
- `knowledge/` - reusable project workflows and research process notes.

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

## Deployment

The production deployment is managed by Vercel from the `frontend/` directory.

Expected Vercel settings:

- Framework preset: Vite
- Root directory: `frontend`
- Install command: `npm install`
- Build command: `npm run build`
- Output directory: `dist`
