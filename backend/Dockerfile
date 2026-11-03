# Образ бэкенда chat-anon.
# ВНИМАНИЕ (локальная разработка на Windows в этой корпоративной сети):
# подключения к PostgreSQL с хоста сбрасываются перехватчиком трафика,
# поэтому миграции и приложение запускаются ВНУТРИ docker-сети —
# контейнер backend ходит в БД напрямую по имени сервиса postgres:5432.
FROM python:3.13-slim

WORKDIR /app

# сначала только зависимости — слой кэшируется при неизменном requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# код бэкенда (контекст сборки — корень репозитория)
COPY backend/ .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
