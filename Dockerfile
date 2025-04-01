
FROM python:3.9-slim


ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
ENV PORT=8080


WORKDIR $APP_HOME


COPY requirements.txt ./


RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8080


CMD ["gunicorn", "-b", "0.0.0.0:8080", "--workers=1", "--threads=8", "--timeout=0", "main:app"]