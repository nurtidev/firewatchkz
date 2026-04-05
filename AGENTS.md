# AGENTS.md — FireWatch Agent Instructions

> This file is auto-loaded by OpenAI Codex CLI and compatible AI coding agents.
> It mirrors CLAUDE.md but is written for agents that don't auto-load CLAUDE.md.

---

## First Thing to Do Each Session

1. Read `CONTEXT.md` — product vision, stack, data model, key decisions
2. Read `TASKS.md` — pick an available task (status `[ ]` with no unmet dependencies)
3. Run `git status` to understand current repo state

---

## Project in One Sentence

FireWatch is a multi-city B2G SaaS platform that gives fire departments AI-powered predictive analytics — FastAPI backend + Next.js frontend, deployed on Railway.

---

## How to Pick Up a Task

1. Find a task in `TASKS.md` with status `[ ]`
2. Check the **Depends on** field — all listed tasks must be `[x]` before you start
3. Read the full task description — acceptance criteria are the definition of done
4. Implement only what is described. No extra features, no refactoring of untouched code
5. Mark the task `[x]` in `TASKS.md` when done

**First tasks available immediately (no dependencies):**
- `A-1` — Backend project scaffold
- `A-2` — Synthetic data generator
- `B-1` — Frontend project scaffold
- `C-1` — Astana districts GeoJSON

These four can run in parallel across separate agents.

---

## Stack (do not change)

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI 0.115, Uvicorn |
| Data | Pandas 2.2, statsmodels 0.14, NumPy 1.26 |
| AI | Anthropic SDK — model `claude-haiku-4-5` |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Charts | Recharts |
| Map | react-leaflet + Leaflet |
| Deploy | Railway (two services: `backend/` and `frontend/`) |

---

## Conventions

- Variable names and comments: **English**
- UI strings (labels, placeholders, messages): **Russian**
- API prefix: `/api/v1/`
- City is always a **query param**: `?city=astana` — never in the URL path
- No database for MVP — CSV files loaded into Pandas DataFrames at startup
- No ORM

---

## Project Structure

```
firewatchkz/
├── AGENTS.md           ← you are here
├── CLAUDE.md           ← same instructions for Claude Code
├── CONTEXT.md          ← full project context (read this)
├── TASKS.md            ← task board (update when done)
├── README.md
├── .gitignore
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── routers/        ← one file per domain
│   ├── services/       ← data_loader, forecaster, claude_client, telegram_service
│   └── scripts/        ← generate_data.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/        ← api.ts, types.ts
│   │   └── context/    ← CityContext.tsx
│   └── package.json
└── data/
    └── sample/         ← committed CSV seed data
```

---

## Environment Variables

**Backend `.env`:**
```
ANTHROPIC_API_KEY=
TELEGRAM_BOT_TOKEN=     # optional — app must start without it
TELEGRAM_CHAT_ID=
DEFAULT_CITY=astana
PORT=8000
```

**Frontend `.env.local`:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running Locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## Do Not

- Add features not listed in `TASKS.md`
- Add a database (Postgres, SQLite, etc.)
- Change the tech stack
- Commit `.env` files
- Commit CSV files outside `data/sample/`
- Use "Astana" in product branding — it's only a test city for dev data
