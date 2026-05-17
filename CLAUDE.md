# CLAUDE.md — FireWatch Project Instructions

> This file is auto-loaded by Claude Code at the start of every session.
> It contains standing instructions, conventions, and shortcuts for this project.

---

## First Thing to Do Each Session

1. Read `CONTEXT.md` — product vision, stack, data model, key decisions
2. Read `TASKS.md` — check what's done and what's next
3. Check git status to understand current state

---

## Project in One Sentence

FireWatch is a multi-city B2G SaaS platform that gives fire departments AI-powered predictive analytics — built on FastAPI + Next.js, deployed on Railway.

---

## Stack (do not change without discussion)

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x async (asyncpg), Alembic, Anthropic SDK
- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS, Recharts, react-leaflet
- **AI model:** `claude-haiku-4-5` (cost-efficient; upgrade to Sonnet only for chat if needed)
- **Database:** PostgreSQL 16 + PostGIS on Railway
- **Workers:** Celery + Redis for async tasks (document processing, risk scoring, backups)
- **Storage:** Cloudflare R2 for documents
- **Deploy:** Railway — two services: `backend/` and `frontend/`

---

## Coding Conventions

- **Language in code:** English (variable names, comments, file names)
- **Language in UI strings:** Russian (user-facing labels, messages, placeholders)
- **API prefix:** `/api/v2/` — v1 has been removed
- **City is always a query param:** `?city=astana` — never in path
- **No extra features** — implement exactly what TASKS.md describes, nothing more
- **Python 3.9 compat:** use `Optional[str]`, `List[str]`, `Dict[str, Any]` from `typing` (not `str | None`)

---

## Key Files

| File | Purpose |
|---|---|
| `CONTEXT.md` | Full project context — read this to understand the why |
| `TASKS.md` | Task board — update status when completing tasks |
| `backend/services/data_loader_v2.py` | Central async data access layer (Postgres) |
| `backend/services/claude_client.py` | All Claude API calls go through here |
| `backend/routers/v2/` | All active API routers |
| `backend/alembic/versions/` | Database migrations (0001–0008) |
| `backend/workers/` | Celery tasks: documents, features, risk, weather, backup |
| `backend/ml/` | XGBoost baseline model + SHAP explanations |
| `backend/docs/` | OBSERVABILITY.md, RECOVERY.md runbooks |

---

## Task Board Rules

- When completing a task, mark it `[x]` in `TASKS.md`
- Do not start a task that has unmet dependencies (listed in each task)

---

## Environment Variables

Backend `.env`:
```
ANTHROPIC_API_KEY=
DATABASE_URL=postgresql+asyncpg://...   # Railway injects this
REDIS_URL=redis://...                   # Railway Redis add-on
TELEGRAM_BOT_TOKEN=                     # optional
TELEGRAM_CHAT_ID=
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=firewatch-documents
R2_PUBLIC_URL=
OPENWEATHERMAP_API_KEY=                 # optional
DEFAULT_CITY=astana
PORT=8000
```

Frontend `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running Locally

```bash
# Backend (requires Docker for Postgres)
docker-compose up -d  # starts Postgres+PostGIS
cd backend && uvicorn main:app --reload

# Frontend
cd frontend && npm run dev

# Tests
cd backend && python3 -m pytest tests/
```

---

## What NOT to Do

- Do not use `/api/v1/` prefix — it has been removed
- Do not use pandas DataFrames in routers — use `data_loader_v2.py` (returns plain dicts)
- Do not use `data_loader.py` — it has been deleted (v1 legacy)
- Do not rename the city "Astana" in data/tests — it's the test city
- Do not change the tech stack without discussion
- Do not add features not listed in TASKS.md without asking
- Do not commit `.env` files
