# AGENTS.md

Файл для ИИ-агентов, работающих с этим проектом. Читатель файла ничего не знает о проекте.

## Обзор проекта

**chat-anon** — анонимный чат без регистрации. Работает сквозной MVP: анон-идентификация, лента сообщений с подгрузкой истории, ответы и цитирование, лайки/дизлайки, файлы (фото с превью и полноэкранным просмотром, аудио/видео с inline-проигрыванием и скачиванием, лимит 100 МБ), удаление и редактирование своих сообщений, WebSocket-доставка, пиксель-арт фронтенд. Весь стек поднимается одной командой `docker compose up -d`.

Исходное описание (на русском) находится в `README.md` — это главный источник требований.

## Функциональные требования (из README.md) и их статус

- Заход без регистрации — **готово** (токен + опциональный никнейм `анон-<число>`).
- Общая лента сообщений — **готово** (REST + WebSocket).
- Текст, эмодзи — **готово**.
- Файлы: фото/аудио/видео до 100 МБ — **готово**: presigned-загрузка напрямую в MinIO через прокси Vite, превью фото с полноэкранным просмотром, аудио/видео проигрываются в чате, всё скачивается.
- Лайки/дизлайки — **готово**.
- Ответы и цитирование (всего/части) — **готово**.
- Удаление и редактирование своих сообщений (текст и вложения) — **готово**; метка «изм.» (`messages.edited_at`), WS-события `message.updated`/`message.deleted`.
- Антиспам — не выбран, отложено.
- Пиксель-арт интерфейс — **готово** (React + CSS, шрифты Press Start 2P / VT323).
- Автохэштеги — отложено. «Читать ветку» — отложено (задел: `messages.reply_to_id`).

## Принятые архитектурные решения

- **Бэкенд:** FastAPI (async) + Uvicorn. **ORM/миграции:** SQLAlchemy 2.0 + asyncpg + Alembic. **Конфигурация:** pydantic-settings (.env, шаблон `.env.example`).
- **Файлы (S3/MinIO):**
  - `POST /api/uploads/presign` — создаёт `Attachment` (message_id NULL) и возвращает presigned PUT URL (15 мин); бэкенд файлы не проксирует;
  - presigned URL подписываются на внутреннем endpoint (`minio:9000`), а в выдачу подставляется `S3_PROXY_BASE_URL` (http://localhost:5173) — Vite проксирует `/chatanon/*` на MinIO (`changeOrigin` ставит Host minio:9000, подпись s3v4 валидна); браузер работает с одним origin, CORS отсутствует;
  - `GET /api/attachments/{id}/file` — 307 на presigned GET (12 ч); `?download=true` — Content-Disposition: attachment (filename* для не-ASCII имён);
  - валидация: MIME image|audio|video, расширение из белого списка, размер ≤ 100 МБ (иначе 415/422).
- **БД:** PostgreSQL 17. Таблицы: `participants`, `messages` (есть `edited_at`), `attachments` (message_id nullable), `reactions`. Счётчики лайков — column_property.
- **API ядра:**
  - `POST /api/participants`, `GET/PATCH /api/participants/me`, заголовок `X-Participant-Token`;
  - `POST /api/messages` (текст ≤4000, reply/quote, `attachment_ids`), `GET /api/messages?before_id=&limit=` (+`next_cursor`, опциональный токен → `my_reaction`);
  - `PATCH /api/messages/{id}` — редактирование своего сообщения (только автор): текст + полный желаемый набор вложений; убранные файлы чистятся из S3 фоновой задачей; WS-событие `message.updated`;
  - `DELETE /api/messages/{id}` — только автор; реакции и вложения каскадом, файлы из S3 чистятся фоновой задачей, ответы сохраняются (reply_to_id → NULL); WS-событие `message.deleted`;
  - `POST /api/messages/{id}/reactions`, `DELETE /api/messages/{id}/reactions/me`;
  - WS `/ws/chat`: события `message.new`, `message.updated`, `message.deleted`, `message.reaction`; менеджер подключений в памяти; клиент шлёт пульс `{event:"ping"}` раз в 10 с.
- **Фронтенд:** React 18 + TS + Vite (dev-сервер в compose, прокси `/api`, `/ws`, `/chatanon` → backend/minio). Состояние — hooks. Общая логика черновиков вложений — `src/uploads.tsx` (`useUploads`, `DraftsView`), используется композером и редактором сообщения. Стили — чистый CSS, пиксель-арт (фото/видео — `image-rendering: auto`).
- **Архитектура:** монолит; миграции/бэкенд/фронтенд внутри docker-сети.

## Текущая структура репозитория

```
chat-anon/
├── README.md           # концепт и требования (на русском)
├── AGENTS.md           # этот файл
├── requirements.txt    # зависимости Python
├── docker-compose.yml  # postgres, minio, backend, frontend
├── .env.example
├── .gitignore
├── .dockerignore
├── backend/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/        # миграции (env.py на async-движок)
│   └── app/
│       ├── main.py     # FastAPI, lifespan (ensure_bucket), роутеры
│       ├── config.py   # pydantic-settings
│       ├── db.py
│       ├── models/     # participant, message, attachment, reaction
│       ├── schemas/    # pydantic-схемы
│       ├── api/        # participants, messages, uploads, ws; deps.py
│       ├── services/   # бизнес-логика сообщений/реакций
│       ├── storage/    # s3.py: presign upload/download, ensure_bucket, delete_object
│       └── ws/         # менеджер WebSocket-подключений
└── frontend/
    ├── Dockerfile      # node:20-alpine, Vite dev; npm через корп. Nexus
    ├── package.json
    ├── index.html
    ├── vite.config.ts  # прокси /api, /ws, /chatanon
    └── src/
        ├── App.tsx
        ├── api.ts      # REST-клиент, uploadFile (presign+PUT), attachmentUrl
        ├── uploads.tsx # useUploads (черновики вложений с загрузкой), DraftsView
        ├── ws.ts
        ├── styles.css
        └── components/ # StartScreen, ChatHeader, MessageItem (вложения+модалка+редактор), Composer
```

Тестовые медиа-файлы лежат в `test-media-files/` (jpeg, mp3, mp4 с кириллическими именами) — удобны для ручных проверок.

## Сборка, запуск и тестирование

Окружение (PowerShell): `.\env\Scripts\Activate.ps1`; в Git Bash: `source env/Scripts/activate`.

1. Весь стек: `docker compose up -d --build` (первый раз; дальше `docker compose up -d`).
   Точка входа: **http://localhost:5173**.
2. Миграции: `docker compose run --rm backend alembic upgrade head`;
   новая: `docker compose run --rm backend alembic revision --autogenerate -m "<описание>"`.
   Важно: правка моделей без применённой миграции роняет API (код ждёт колонку, которой нет в БД) — после изменения моделей миграцию создавать и применять сразу.
3. Код бэкенда меняется без пересборки (volume): `docker compose restart backend`. Фронтенд — hot reload, но после массовых правок надёжнее `docker compose restart frontend` (сброс кэша модулей Vite).
4. Typecheck фронта (с хоста): `cd frontend && npx tsc --noEmit`.
5. Тестов нет; проверка — smoke-сценарии. Важно: **MinIO-ноги (PUT/GET к 9000) проверять синхронным httpx или curl** — асинхронный httpx к порту 9000 на этой машине зависает (проявление связки proactor/asyncio с ретранслятором Docker Desktop; браузер и curl не затронуты).

## Особенности текущей сети/окружения (важно!)

- **Корпоративный перехватчик сбрасывает подключения к PostgreSQL с хоста** — миграции и бэкенд работают внутри docker-сети (`postgres:5432`). HTTP/WS через опубликованные порты проходят.
- Порт **5432 занят системным PostgreSQL** (служба Windows) — контейнер проекта на **5433**.
- **MinIO (bitnamilegacy) не отдаёт CORS-заголовков и не отвечает на preflight** — поэтому presigned-URL выдаются с host Vite и проксируются (`/chatanon` → `minio:9000`, changeOrigin; имя бакета должно совпадать с S3_BUCKET).
- **npm в контейнерах — через корпоративный Nexus** `http://nexus.rw.org/repository/npm/` (plain HTTP): прямой registry.npmjs.org ломается TLS-инспекцией (SELF_SIGNED_CERT_IN_CHAIN). pip хоста — аналогично (nexus.rw.org/repository/python).
- Официальные образы `minio/*` убраны с Docker Hub, quay.io недоступен — используется `bitnamilegacy/minio` (для прода — `quay.io/minio/minio`).
- Сеть до Docker Hub нестабильна — большие pull-ы обрываются, повторяйте `docker compose build`.
- Периодические перезагрузки страницы чата — следить за консолью браузера (F12); на данный момент устранены пульсами WebSocket (см. `main.tsx` и `ws.ts`).

## Язык и соглашения

- Документация и комментарии — на **русском**.
- Зависимости: Python — `requirements.txt`; Node — `frontend/package.json` + `package-lock.json`.
- Обновляйте этот `AGENTS.md` по мере принятия решений.

## Вопросы, требующие проработки (явно отмечены в README)

1. Антиспам-защита — не выбрана, отложено.
2. Автоматическое присвоение хэштегов — отложено.
3. «Читать ветку» — не специфицировано; задел: `messages.reply_to_id`.
