# DevOps Observability Lab

A complete Observability system for a containerized application using Prometheus, Grafana, Loki, and Promtail.

## Quick Start

```bash
docker compose up --build -d
```

Access the services:
- **Application**: http://localhost:5000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Loki**: http://localhost:3100

### Data Flow

1. **Metrics**: The Flask app exposes custom counters (`app_requests_total`, `app_errors_total`) at `/metrics`. Prometheus scrapes this endpoint every 15s.
2. **Logs**: The app writes JSON-structured logs to `/var/log/app/app.log`. Promtail tails this file and pushes logs to Loki.
3. **Visualization**: Grafana queries Prometheus for metrics dashboards and Loki for log exploration.
4. **Alerting**: Prometheus evaluates alert rules every 15s. If `rate(app_errors_total[1m]) > 0.0833` (5 errors/min) for 1 minute, a CRITICAL alert fires.

## Logging Strategy

The application uses **JSON-structured logging** via a custom `JSONLogHandler`. Every log line is a JSON object containing:

```json
{
  "timestamp": "2025-01-01 12:00:00,123",
  "logger": "app",
  "level": "ERROR",
  "message": "Error endpoint called",
  "module": "app",
  "function": "error",
  "line": 72,
  "endpoint": "/error",
  "method": "GET",
  "status": 500,
  "duration_ms": 23.45,
  "error": "Simulated error"
}
```

Promtail tails these files and ships them to Loki, where they are indexed and queryable in Grafana's Explore view or via LogQL.

## Simulating the CRITICAL Alert

### Option 1: Quick script

```bash
./simulate_alert.sh
```

This fires 30 concurrent `/error` requests to spike the error rate above 5/min.

### Option 2: Manual

```bash
# Rapidly hit the error endpoint
for i in $(seq 1 30); do curl -s -o /dev/null http://localhost:5000/error & done; wait
```

### Option 3: Continuous load

```bash
while true; do curl -s -o /dev/null http://localhost:5000/error; sleep 0.5; done
```

### Viewing the Alert

1. Open Grafana at http://localhost:3000 (admin/admin)
2. Navigate to **Alerting** → **Alert rules**
3. The `HighErrorRate` rule will show as **Firing** (pending for 1m, then firing)
4. Check the **Alerting** → **Instances** tab for active alert instances

## Screenshots

### Grafana Dashboard
![Grafana Dashboard](screenshots/grafana-dashboard.png)

### Log Analysis (Grafana Explore with Loki)
![Log Analysis](screenshots/loki-logs.png)

### Alerting Rules
![Alerting Rules](screenshots/alerting-rules.png)

## Analysis

### Why is JSON-structured logging more efficient than plain text logs?

JSON-structured logging is more efficient because:

1. **Machine-parseable**: Tools like Loki, Elasticsearch, and log aggregators can natively parse JSON fields without custom regex patterns, reducing CPU overhead during ingestion.
2. **Queryable fields**: Each field (e.g., `level`, `endpoint`, `duration_ms`) becomes an indexed key, enabling fast filtering (LogQL: `{job="app"} |= "ERROR"` or `{job="app"} | json | level="ERROR"`).
3. **Consistent schema**: Structured logs enforce a uniform schema across services, making it trivial to correlate fields, build dashboards, and set alerts based on specific log attributes.
4. **No parsing ambiguity**: Plain text logs require fragile regex or grok patterns that break when log format changes; JSON avoids this entirely.

### What is the fundamental technical difference between Prometheus (metrics) and your chosen logging system?

| Dimension | Prometheus (Metrics) | Loki (Logs) |
|-----------|---------------------|-------------|
| **Data model** | Numeric time-series with labels | Immutable log streams with metadata labels |
| **Storage** | Pull-based; TSDB with periodic compaction | Push-based; compressed, object-store friendly chunks |
| **Query language** | PromQL — aggregate, rate, histogram quantiles | LogQL — log filtering, pattern matching, metrics from logs |
| **Cardinality** | Labels should be bounded; high cardinality causes memory pressure | Labels are metadata; high cardinality is more tolerable |
| **Retention** | Configurable per-series; typically days to weeks | Designed for long-term retention with cheaper object storage backends |
| **Primary use** | Alerting on rate/trends, capacity planning, SLOs | Debugging, audit trails, detailed event inspection |

The fundamental difference: **Prometheus tracks the *health and behavior* of systems through numeric aggregations** (counts, rates, histograms) that are pre-computed at scrape time. **Loki stores *individual events* as raw log lines**, optimized for search and filtering rather than numerical aggregation. You design Prometheus queries to answer "what is my error rate?" and Loki queries to answer "what exactly was in the error at 12:00:03?"

### How would you handle long-term log retention (e.g., 6 months) without depleting disk resources?

1. **Use object storage as the backend**: Configure Loki's `filesystem` storage to use S3/GCS/MinIO instead of local disk. Object storage is cheap, scalable, and built for long-term data.

2. **Implement log lifecycle policies with retention and compaction**:
   - **Hot storage** (fast disk): Recent logs (e.g., last 7 days) for fast querying
   - **Warm/Cold storage** (object store): Older logs (7 days to 6 months) with slower access
   - Use Loki's `retention_period` and `compactor` to delete data past the retention window

3. **Use structured log levels to tier retention**:
   - Keep all logs for 30 days
   - Keep `WARN`+ and `ERROR`+ logs for 6 months
   - Filter and discard `DEBUG`/`INFO` logs after a shorter period
   - Use Loki's `deletion_mode` to programmatically delete low-value log streams

4. **Aggregate and downsample**:
   - Use LogQL queries (`rate`, `count_over_time`) to produce derived metrics
   - Store aggregated metrics (e.g., error counts per hour) in Prometheus as a long-term summary
   - Delete raw logs after 90 days, keeping only summaries for older periods

5. **Compress and deduplicate**: Loki already compresses chunks. Enable `chunk_target_size` and tune `chunk_compression` to maximize compression ratios (often 5:1 to 10:1).

Example Loki S3 configuration snippet:

```yaml
storage_config:
  aws:
    s3: s3://my-bucket/loki
    s3forcepathstyle: true
  tsdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
```
