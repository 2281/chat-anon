# chat-anon

Анонимный чат без регистрации и паролей. Вход — по email (он же идентификатор пользователя: повторный вход с тем же email возвращает ту же учётную запись), никнейм необязателен — по умолчанию `анон-<число>`.

## Возможности

- общая лента сообщений с подгрузкой истории и доставкой по WebSocket;
- треды: ответы отображаются как комментарии под сообщением с любой вложенностью; длинные треды свёрнуты (корень + первый ответ), разворачиваются кнопкой «▸ …»;
- цитирование сообщения целиком или выделенного фрагмента;
- лайки/дизлайки;
- уведомления: об ответах в ваших ветках и об оценках ваших сообщений; колокольчик с числом непрочитанных, переход к сообщению из уведомления;
- файлы: фото (превью + полноэкранный просмотр), аудио/видео (inline-проигрывание), скачивание, лимит 100 МБ;
- редактирование и удаление своих сообщений (метка «изм.»);
- пиксель-арт интерфейс (шрифты Press Start 2P / VT323).

## Стек

**Бэкенд** — Python 3.13, FastAPI + Uvicorn (async), SQLAlchemy 2.0 + asyncpg, Alembic (миграции), pydantic / pydantic-settings, aioboto3 (S3).

**Фронтенд** — React 18 + TypeScript + Vite (dev-сервер), состояние на hooks, чистый CSS.

**Инфраструктура** — PostgreSQL 17 (данные), MinIO (S3-совместимое хранилище файлов), Docker Compose. Загрузка файлов — напрямую в MinIO по presigned URL через прокси Vite (без CORS).

## Структура проекта

```
chat-anon/
├── docker-compose.yml             # postgres, minio, backend, frontend
├── docker-compose_local-repo.yml  # override: сборка через Nexus (корп. сеть)
├── requirements.txt               # зависимости Python
├── .env.example                   # шаблон конфигурации
├── backend/
│   ├── Dockerfile                 # pip с pypi.org
│   ├── Dockerfile_local-repo      # pip из Nexus (корп. сеть)
│   ├── alembic/                   # миграции БД
│   └── app/
│       ├── main.py                # FastAPI, роутеры
│       ├── config.py              # pydantic-settings (.env)
│       ├── models/                # participant, message, attachment, reaction, notification
│       ├── schemas/               # pydantic-схемы
│       ├── api/                   # participants, messages, uploads, notifications, ws
│       ├── services/              # бизнес-логика сообщений/реакций/уведомлений
│       ├── storage/s3.py          # presigned URL, бакет, удаление объектов
│       └── ws/                    # менеджер WebSocket-подключений
└── frontend/
    ├── Dockerfile                 # npm ci из registry.npmjs.org
    ├── Dockerfile_local-repo      # npm через Nexus (корп. сеть)
    ├── vite.config.ts             # прокси /api, /ws, /chatanon → backend/minio
    └── src/
        ├── App.tsx                # лента, дерево тредов, уведомления
        ├── api.ts                 # REST-клиент, загрузка файлов
        ├── uploads.tsx            # черновики вложений (useUploads, DraftsView)
        ├── ws.ts                  # WebSocket с переподключением
        └── components/            # StartScreen, ChatHeader, MessageItem, Composer
```

## Запуск

Требуется только Docker с Compose.

```bash
docker compose up -d --build                       # первый запуск (дальше: up -d)
docker compose run --rm backend alembic upgrade head   # миграции БД
```

Точка входа: **http://localhost:5173**. С телефона по Wi-Fi: **http://\<IP-компа\>:5173** (все ссылки относительные; проверьте, что файрвол пропускает порт 5173).

Важно: миграции применяются вручную — после обновления кода с новыми миграциями выполняйте `alembic upgrade head` (правка моделей без миграции роняет API).

### Порты

| Сервис    | Порт хоста | Назначение                          |
|-----------|------------|-------------------------------------|
| frontend  | 5173       | точка входа (Vite dev-сервер)       |
| backend   | 8000       | REST API и WebSocket                |
| postgres  | 5433       | БД (5433, чтобы не конфликтовать с локальным PostgreSQL) |
| minio     | 9000/9001  | S3 API / веб-консоль (minioadmin/minioadmin) |

### Корпоративная сеть (Nexus)

Если pypi.org и registry.npmjs.org недоступны (TLS-инспекция), есть вариант сборки через локальные репозитории:

```bash
docker compose -f docker-compose_local-repo.yml up -d --build
```

Файл самодостаточен (подключает основной через `include`), двухфайловая форма `docker compose -f docker-compose.yml -f docker-compose_local-repo.yml up -d --build` даёт тот же результат. Требуется Docker Compose >= 2.20.

### Разработка

- код бэкенда смонтирован volume'ом — после правок: `docker compose restart backend`;
- фронтенд — hot reload; после массовых правок надёжнее `docker compose restart frontend`;
- новая миграция: `docker compose run --rm backend alembic revision --autogenerate -m "<описание>"`;
- typecheck фронта: `docker compose exec frontend npx tsc --noEmit`.

Конфигурация — через переменные окружения (шаблон `.env.example`): строка подключения к БД, endpoint'ы S3, режим прокси для presigned URL. Значения по умолчанию соответствуют docker-compose.yml, `.env` не обязателен.
