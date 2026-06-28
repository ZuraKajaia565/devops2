# Incident Response and Recovery

## Service Objective

The local observability stack should keep the Flask application available during normal development with a target availability of 99% while containers are running. The `/health` endpoint, Prometheus scrape status, Grafana dashboards, and Loki logs are the primary evidence for availability.

## Detection

1. Open Grafana at `http://localhost:3000`.
2. Check the application dashboard for request rate and error counters.
3. Check Prometheus alert rules for `HighErrorRate`.
4. Query Loki logs in Grafana Explore using `{job="app"}` and filter for `ERROR`.

## Triage

1. Run `.\scripts\validate.ps1`.
2. Check service state with `docker compose ps`.
3. Inspect recent app logs with `docker compose logs --tail=100 app`.
4. Inspect Prometheus targets at `http://localhost:9090/targets`.

## Recovery

1. Restart the unhealthy service: `docker compose restart app`.
2. If metrics or logs are stale, restart the collector: `docker compose restart prometheus promtail`.
3. If the whole environment is inconsistent, recreate it with `docker compose up --build -d`.
4. Re-run `.\scripts\validate.ps1` and confirm Grafana dashboards return data.

## Rollback

1. Find the last known good commit: `git log --oneline`.
2. Create a rollback branch: `git switch -c rollback/<short-description>`.
3. Revert the faulty commit without rewriting history: `git revert <commit-sha>`.
4. Rebuild and verify locally: `.\scripts\setup.ps1`.
5. Push the rollback branch and open a pull request.

## Post-Incident Review

Record the trigger, user impact, timeline, recovery command, and follow-up action in the project issue tracker or README notes. Add or update an alert when an incident was not detected automatically.
