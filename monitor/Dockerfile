FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home sentinel
COPY ml ./ml
COPY monitor ./monitor
COPY data/train.csv ./data/train.csv
RUN python -m ml.train && chown -R sentinel:sentinel /app/artifacts
USER sentinel
EXPOSE 8000 8001
HEALTHCHECK --interval=10s --start-period=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/readyz',timeout=2)"
CMD ["python", "-m", "monitor.monitor"]
