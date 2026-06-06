import os
import random
import time
import logging
import json
import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, Response
from prometheus_client import Counter, generate_latest, REGISTRY, CONTENT_TYPE_LATEST
import structlog

app = Flask(__name__)

app_requests_total = Counter("app_requests_total", "Total application requests", ["endpoint", "method"])
app_errors_total = Counter("app_errors_total", "Total application errors", ["endpoint", "method"])

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

LOG_DIR = "/var/log/app"
os.makedirs(LOG_DIR, exist_ok=True)

class JSONLogHandler(logging.Handler):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    def emit(self, record):
        log_entry = {
            "timestamp": datetime.datetime.now(ZoneInfo("Asia/Tbilisi")).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "endpoint"):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "duration"):
            log_entry["duration_ms"] = record.duration
        if hasattr(record, "error"):
            log_entry["error"] = record.error
        line = json.dumps(log_entry)
        with open(self.filename, "a") as f:
            f.write(line + "\n")
        print(line, flush=True)

json_handler = JSONLogHandler(os.path.join(LOG_DIR, "app.log"))
logging.getLogger().addHandler(json_handler)
logging.getLogger().setLevel(logging.INFO)

werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.handlers = [json_handler]
werkzeug_logger.setLevel(logging.INFO)


@app.route("/")
def home():
    app_requests_total.labels(endpoint="/", method="GET").inc()
    duration = random.uniform(0.01, 0.1)
    time.sleep(duration)

    extra = {"endpoint": "/", "method": "GET", "status": 200, "duration": round(duration * 1000, 2)}
    logging.getLogger("app").info("Home endpoint called", extra=extra)
    return {"message": "OK", "endpoint": "/"}


@app.route("/error")
def error():
    app_requests_total.labels(endpoint="/error", method="GET").inc()
    app_errors_total.labels(endpoint="/error", method="GET").inc()

    duration = random.uniform(0.01, 0.05)
    time.sleep(duration)

    extra = {"endpoint": "/error", "method": "GET", "status": 500, "duration": round(duration * 1000, 2), "error": "Simulated error"}
    logging.getLogger("app").error("Error endpoint called", extra=extra)
    return {"message": "ERROR", "endpoint": "/error"}, 500


@app.route("/health")
def health():
    return {"status": "healthy"}


@app.route("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
