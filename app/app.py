import os
import random
import time
import logging
import json
import datetime
from markupsafe import escape
from flask import Flask, request, Response
from prometheus_client import Counter, generate_latest, REGISTRY, CONTENT_TYPE_LATEST
import structlog

app = Flask(__name__)

app_requests_total = Counter("app_requests_total", "Total application requests", ["endpoint", "method"])
app_errors_total = Counter("app_errors_total", "Total application errors", ["endpoint", "method"])

APP_UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DevOps Observability App</title>
  <style>
    :root { color-scheme: light; font-family: Arial, sans-serif; }
    body { margin: 0; background: #f5f7fb; color: #18202f; }
    main { max-width: 960px; margin: 0 auto; padding: 40px 20px; }
    header { margin-bottom: 28px; }
    h1 { margin: 0 0 8px; font-size: 34px; }
    p { line-height: 1.55; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .card { background: #fff; border: 1px solid #dbe2ef; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(31, 42, 68, 0.06); }
    .status { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; color: #116a3a; }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #1fad63; }
    a { color: #2457c5; font-weight: 700; text-decoration: none; }
    a:hover { text-decoration: underline; }
    code { background: #eef2f7; border-radius: 4px; padding: 2px 5px; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>DevOps Observability App</h1>
      <p class="status"><span class="dot"></span> Application UI is running</p>
      <p>This screen is the human-facing app page. The project also exposes JSON APIs, Prometheus metrics, structured logs, and alert simulation endpoints.</p>
    </header>
    <section class="grid">
      <div class="card">
        <h2>Application</h2>
        <p>API status: <code>/health</code></p>
        <p><a href="/health">Open health check</a></p>
      </div>
      <div class="card">
        <h2>Metrics</h2>
        <p>Prometheus scrapes <code>/metrics</code> every 15 seconds.</p>
        <p><a href="/metrics">Open metrics</a></p>
      </div>
      <div class="card">
        <h2>Alert Test</h2>
        <p>The <code>/error</code> endpoint increments the error counter and writes an error log.</p>
        <p><a href="/error">Trigger one error</a></p>
      </div>
      <div class="card">
        <h2>Dynamic Route</h2>
        <p>Try a personalized endpoint.</p>
        <p><a href="/hello/student">Open /hello/student</a></p>
      </div>
      <div class="card">
        <h2>Feedback Form</h2>
        <p>Submit a message through an input form.</p>
        <p><a href="/feedback">Open feedback form</a></p>
      </div>
      <div class="card">
        <h2>Observability</h2>
        <p>Use Grafana for dashboards and Loki log exploration.</p>
        <p><a href="http://localhost:3000">Open Grafana</a></p>
      </div>
    </section>
  </main>
</body>
</html>"""

FEEDBACK_FORM_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feedback</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f5f7fb; color: #18202f; }
    main { max-width: 720px; margin: 0 auto; padding: 40px 20px; }
    form { display: grid; gap: 14px; background: #fff; border: 1px solid #dbe2ef; border-radius: 8px; padding: 20px; }
    label { font-weight: 700; }
    input, textarea { width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #b7c3d7; border-radius: 6px; font: inherit; }
    button { width: max-content; padding: 10px 14px; border: 0; border-radius: 6px; background: #2457c5; color: #fff; font-weight: 700; cursor: pointer; }
    a { color: #2457c5; font-weight: 700; text-decoration: none; }
  </style>
</head>
<body>
  <main>
    <h1>Feedback</h1>
    <form method="post" action="/feedback">
      <label for="name">Name</label>
      <input id="name" name="name" required maxlength="80">
      <label for="message">Message</label>
      <textarea id="message" name="message" required maxlength="500" rows="5"></textarea>
      <button type="submit">Submit feedback</button>
    </form>
    <p><a href="/ui">Back to app UI</a></p>
  </main>
</body>
</html>"""

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

LOG_DIR = os.getenv("LOG_DIR", "/var/log/app")
os.makedirs(LOG_DIR, exist_ok=True)
APP_TIMEZONE = datetime.timezone(datetime.timedelta(hours=4), "Asia/Tbilisi")

class JSONLogHandler(logging.Handler):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    def emit(self, record):
        log_entry = {
            "timestamp": datetime.datetime.now(APP_TIMEZONE).isoformat(),
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
    return {"message": "OK", "endpoint": "/", "ui": "/ui"}


@app.route("/ui")
def ui():
    app_requests_total.labels(endpoint="/ui", method="GET").inc()
    extra = {"endpoint": "/ui", "method": "GET", "status": 200, "duration": 0}
    logging.getLogger("app").info("UI endpoint called", extra=extra)
    return Response(APP_UI_HTML, mimetype="text/html")


@app.route("/hello/<name>")
def hello(name):
    app_requests_total.labels(endpoint="/hello/<name>", method="GET").inc()
    safe_name = escape(name)
    extra = {"endpoint": "/hello/<name>", "method": "GET", "status": 200, "duration": 0}
    logging.getLogger("app").info("Dynamic hello endpoint called", extra=extra)
    return {"message": f"Hello, {safe_name}!", "endpoint": "/hello/<name>"}


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    app_requests_total.labels(endpoint="/feedback", method=request.method).inc()
    if request.method == "GET":
        extra = {"endpoint": "/feedback", "method": "GET", "status": 200, "duration": 0}
        logging.getLogger("app").info("Feedback form viewed", extra=extra)
        return Response(FEEDBACK_FORM_HTML, mimetype="text/html")

    name = request.form.get("name") or (request.get_json(silent=True) or {}).get("name", "")
    message = request.form.get("message") or (request.get_json(silent=True) or {}).get("message", "")
    name = str(name).strip()
    message = str(message).strip()
    if not name or not message:
        extra = {"endpoint": "/feedback", "method": "POST", "status": 400, "duration": 0, "error": "Missing name or message"}
        logging.getLogger("app").warning("Invalid feedback submitted", extra=extra)
        return {"status": "error", "message": "name and message are required"}, 400

    extra = {"endpoint": "/feedback", "method": "POST", "status": 201, "duration": 0}
    logging.getLogger("app").info("Feedback submitted", extra=extra)
    return {"status": "received", "name": name, "message_length": len(message)}, 201


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
