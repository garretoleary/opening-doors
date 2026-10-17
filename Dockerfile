FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY opening_doors ./opening_doors
COPY web ./web
COPY rules ./rules
COPY README.md .
ENV OPENING_DOORS_HOST=0.0.0.0 PORT=8765 OPENING_DOORS_DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "-m", "web.server"]
