# FireWatch Observability — Railway → Grafana Cloud

## 1. Connecting Railway Metrics to Grafana Cloud

Railway exposes a Prometheus-compatible `/metrics` endpoint via `prometheus-fastapi-instrumentator`.
To scrape these metrics into Grafana Cloud:

1. In Grafana Cloud, navigate to **Connections → Add new connection → Prometheus**.
2. Copy the **Remote Write URL** (format: `https://prometheus-prod-XX-X.grafana.net/api/prom/push`).
3. In your Railway backend service, add these environment variables (no secrets in this file):
   - `GRAFANA_REMOTE_WRITE_URL` — the Remote Write URL from step 2
   - `GRAFANA_USER` — your Grafana Cloud numeric user ID
   - `GRAFANA_API_KEY` — a Grafana Cloud API key with `MetricsPublisher` role
4. Deploy a sidecar **Grafana Agent** service on Railway that scrapes `http://backend:8000/metrics`
   every 15 s and remote-writes to Grafana Cloud using the credentials above.
   Use the official `grafana/agent` Docker image with a minimal `agent.yaml`:

```yaml
metrics:
  global:
    scrape_interval: 15s
    remote_write:
      - url: ${GRAFANA_REMOTE_WRITE_URL}
        basic_auth:
          username: ${GRAFANA_USER}
          password: ${GRAFANA_API_KEY}
  configs:
    - name: firewatch
      scrape_configs:
        - job_name: firewatch-backend
          static_configs:
            - targets: ["backend:8000"]
```

## 2. Dashboards to Create

### Dashboard A — Request Rate / Latency / Errors
Panels:
- **Request rate** (rpm): `rate(http_requests_total[1m]) * 60`
- **P50 / P95 / P99 latency**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
- **Error rate (5xx)**: `rate(http_requests_total{status=~"5.."}[1m]) / rate(http_requests_total[1m])`
- **Error rate (4xx)**: same pattern with `4..`

### Dashboard B — Celery Throughput
Panels (sourced from structlog JSON lines exported via Loki, or via a custom Celery Prometheus exporter):
- **Tasks started per minute** by `task_name`
- **Tasks succeeded per minute** by `task_name`
- **Tasks failed per minute** by `task_name`
- **Median / P95 task duration** (`duration_ms` from `celery_task_success` log events)

### Dashboard C — Claude API Cost per Day
Panels (sourced from Loki log queries on `claude_api_call` JSON events):
- **Total cost USD / day**: `sum_over_time(cost_usd[1d])`
- **Input vs output tokens / day**
- **Calls per hour** heatmap

## 3. Alert Rule — Error Rate > 5 % for 5 min → Telegram

In Grafana Alerting, create a rule:

```
Condition:
  rate(http_requests_total{status=~"5.."}[1m])
    /
  rate(http_requests_total[1m])
  > 0.05

For: 5m

Contact point: Telegram
  Bot token: ${TELEGRAM_BOT_TOKEN}   (set in Railway env, not hardcoded)
  Chat ID:   ${TELEGRAM_CHAT_ID}

Message template (Russian):
  🚨 FireWatch: уровень ошибок {{ $value | printf "%.1f%%" }} за последние 5 минут.
  Сервис: {{ $labels.job }}
  Действие: проверьте Railway логи и статус деплоя.
```

Store the Telegram bot token and chat ID only as Railway environment variables — never commit them to the repository.
