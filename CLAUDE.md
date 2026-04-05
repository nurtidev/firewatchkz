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

- **Backend:** Python 3.11, FastAPI, Pandas, statsmodels, Anthropic SDK
- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS, Recharts, react-leaflet
- **AI model:** `claude-haiku-4-5` (cost-efficient; upgrade to Sonnet only for chat if needed)
- **Deploy:** Railway — two services: `backend/` and `frontend/`
- **No database for MVP** — CSV → Pandas DataFrames loaded at startup

---

## Coding Conventions

- **Language in code:** English (variable names, comments, file names)
- **Language in UI strings:** Russian (user-facing labels, messages, placeholders)
- **API prefix:** `/api/v1/`
- **City is always a query param:** `?city=astana` — never in path
- **No extra features** — implement exactly what TASKS.md describes, nothing more
- **No ORM, no database** — raw Pandas for MVP

---

## Key Files

| File | Purpose |
|---|---|
| `CONTEXT.md` | Full project context — read this to understand the why |
| `TASKS.md` | Task board — update status when completing tasks |
| `backend/services/data_loader.py` | Central data access layer |
| `backend/services/claude_client.py` | All Claude API calls go through here |
| `data/sample/astana_incidents.csv` | Generated demo data (committed) |

---

## Task Board Rules

- When completing a task, mark it `[x]` in `TASKS.md`
- Do not start a task that has unmet dependencies (listed in each task)
- Tasks A-1, A-2, B-1, C-1 can all start in parallel — no dependencies

---

## Environment Variables

Backend `.env`:
```
ANTHROPIC_API_KEY=
TELEGRAM_BOT_TOKEN=     # optional, app must start without it
TELEGRAM_CHAT_ID=
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
# Backend
cd backend && uvicorn main:app --reload

# Frontend
cd frontend && npm run dev
```

---

## What NOT to Do

- Do not rename the city "Astana" to anything else in data/tests — it's the test city
- Do not add a database until MVP is shipped
- Do not change the tech stack
- Do not add features not listed in TASKS.md without asking the user
- Do not commit `.env` files or CSV files outside `data/sample/`
