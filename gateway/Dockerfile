FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lti_gateway ./lti_gateway
RUN useradd --system --uid 10001 gateway && mkdir /data && chown gateway /data
USER gateway
EXPOSE 8090
CMD ["gunicorn", "--bind", "0.0.0.0:8090", "--workers", "2", "lti_gateway.app:create_app()"]
