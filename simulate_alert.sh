#!/bin/bash
# Simulates a CRITICAL alert by hitting /error rapidly
# Requires curl and jq (optional)
echo "Triggering errors to simulate CRITICAL alert..."
echo "Hitting /error endpoint 30 times with concurrency..."

for i in $(seq 1 30); do
    curl -s -o /dev/null http://localhost:5000/error &
done

wait
echo ""
echo "Done! Check Grafana at http://localhost:3000 (admin/admin)"
echo "Alerting > Alert rules to see the HighErrorRate alert."
echo ""
echo "To verify the error rate, run:"
echo "  curl -s http://localhost:9090/api/v1/query?query=rate(app_errors_total[1m])*60"
