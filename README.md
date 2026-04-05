# FireWatch — AI Platform for Fire Incident Prevention

> Предиктивная аналитика и AI-рекомендации для служб пожарной безопасности.  
> Multi-city SaaS. Одно развёртывание — любой город.

---

## Что делает платформа

FireWatch превращает исторические данные о пожарах в конкретные действия:

- **Инспектор** — киллер-фича: AI анализирует 5 факторов риска по каждому району и выдаёт приоритизированный список превентивных проверок (critical / high / medium / low)
- **Прогноз** — Holt-Winters ETS, горизонт 3/6/12 месяцев, R²=0.82, доверительный интервал 80%
- **Карта рисков** — интерактивная Leaflet-карта с цветовой шкалой по районам
- **AI Рекомендации** — 5 конкретных мер от Claude AI с приоритетами и ожидаемым эффектом
- **AI Аналитик** — чат на русском/казахском по данным о пожарах города
- **KPI дашборд** — пожары с начала года, ущерб в тенге, потенциал сокращения
- **Telegram алерты** — 4-уровневые оповещения + ежедневный дайджест
- **Выбор города** — переключение через топбар, архитектура city-agnostic

---

## Стек

| Слой | Технология |
|---|---|
| Frontend | Next.js 15 · React 19 · TypeScript · Tailwind CSS |
| Карта | react-leaflet + GeoJSON |
| Графики | Recharts |
| Backend | Python 3.11 · FastAPI · Uvicorn |
| Аналитика | Pandas · statsmodels (Holt-Winters ETS) |
| AI | Anthropic Claude API — `claude-haiku-4-5` |
| Scheduler | APScheduler |
| Деплой | Railway (два сервиса: `frontend` + `backend`) |

---

## Структура проекта

```
firewatchkz/
├── frontend/
│   └── src/
│       ├── app/
│       │   └── dashboard/
│       │       ├── page.tsx           # KPI + карта + прогноз + рекомендации
│       │       ├── inspector/         # Инспектор (киллер-фича)
│       │       ├── map/               # Карта рисков
│       │       ├── forecast/          # Прогноз инцидентов
│       │       ├── recommendations/   # AI рекомендации
│       │       ├── chat/              # AI аналитик
│       │       └── alerts/            # Telegram настройки
│       ├── components/
│       │   ├── layout/                # TopBar, Sidebar, StatCard
│       │   ├── map/RiskMap.tsx
│       │   ├── charts/                # ForecastChart, IncidentsByDistrict
│       │   ├── ai/                    # ChatPanel, RecommendationCard
│       │   └── telegram/
│       ├── context/CityContext.tsx
│       └── lib/                       # api.ts, types.ts
│
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── inspector.py               # Инспектор — 5 факторов риска
│   │   ├── forecast.py                # Holt-Winters прогноз
│   │   ├── incidents.py               # risk-map + список инцидентов
│   │   ├── kpi.py                     # KPI метрики
│   │   ├── recommendations.py         # Claude AI рекомендации
│   │   ├── chat.py                    # AI аналитик
│   │   ├── cities.py                  # список городов + GeoJSON
│   │   └── telegram.py               # алерты
│   ├── services/
│   │   ├── data_loader.py             # загрузка CSV → DataFrame, кэш
│   │   ├── forecaster.py              # Holt-Winters wrapper
│   │   ├── claude_client.py           # Anthropic SDK
│   │   └── telegram_service.py
│   ├── scripts/
│   │   └── generate_data.py           # генератор синтетических данных
│   └── data/
│       ├── geojson/astana_districts.geojson
│       └── sample/                    # seed CSV (в git)
│
├── data/sample/astana_incidents.csv   # 834 инцидента, 3 года
│
├── CLAUDE.md     # инструкции для Claude Code
├── AGENTS.md     # инструкции для Codex и других агентов
├── CONTEXT.md    # контекст проекта
└── TASKS.md      # таск-борд
```

---

## Быстрый старт

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # добавь ANTHROPIC_API_KEY
uvicorn main:app --reload
# http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
# .env.local уже настроен на localhost:8000
npm run dev
# http://localhost:3000
```

---

## Тестовые данные

834 синтетических инцидента по Астане за 3 года (2023–2026):
- 5 районов: Есіл, Алматы, Байқоңыр, Сарыарқа, Нұра
- Сезонность: пики в январе–феврале и мае–июне
- Суммарный ущерб: ₸14.1 млрд

Перегенерировать:
```bash
cd backend
python3 scripts/generate_data.py --city astana --years 3 --output ../data/sample/astana_incidents.csv
```

Данные для продакшена: [data.egov.kz](https://data.egov.kz) (открытые данные ДЧС РК).

---

## Деплой на Railway

1. Запушить репо на GitHub
2. Railway → New Project → Deploy from GitHub
3. Два сервиса: `backend/` и `frontend/`
4. Переменные окружения:

**backend:**
```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=...       (опционально)
TELEGRAM_CHAT_ID=...         (опционально)
```

**frontend:**
```
NEXT_PUBLIC_API_URL=https://<твой-backend>.up.railway.app
```

---

## API эндпоинты

```
GET  /health
GET  /api/v1/cities
GET  /api/v1/cities/{id}
GET  /api/v1/cities/{id}/geojson
GET  /api/v1/kpi?city=
GET  /api/v1/risk-map?city=
GET  /api/v1/incidents?city=&district=&limit=
GET  /api/v1/forecast?city=&months=3|6|12
GET  /api/v1/inspector?city=
GET  /api/v1/recommendations?city=
POST /api/v1/chat
GET  /api/v1/telegram/config
POST /api/v1/telegram/test?city=
```

---

## Роадмап

- [x] MVP — дашборд, прогноз, карта рисков, AI чат
- [x] Инспектор — превентивные проверки по факторам риска
- [ ] Пожарные части и гидранты на карте
- [ ] Авторизация и роли (диспетчер / аналитик / admin)
- [ ] Реальные данные с data.egov.kz
- [ ] Мобильное приложение для диспетчеров
- [ ] Интеграция с системой 112

---

## Лицензия

Proprietary. All rights reserved.
