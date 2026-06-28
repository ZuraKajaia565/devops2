FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN addgroup -S appuser \
    && adduser -S -G appuser appuser \
    && mkdir -p /var/log/app \
    && chown -R appuser:appuser /app /var/log/app
USER appuser
EXPOSE 5000
CMD ["python", "app.py"]
