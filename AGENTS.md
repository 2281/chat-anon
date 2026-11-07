# AGENTS.md

Файл для ИИ-агентов, работающих с этим проектом. Читатель файла ничего не знает о проекте.

## Обзор проекта

**chat-anon** — анонимный чат без регистрации. Работает сквозной MVP: анон-идентификация, лента сообщений с подгрузкой истории, ответы и цитирование, лайки/дизлайки, файлы (фото с превью и полноэкранным просмотром, аудио/видео с inline-проигрыванием и скачиванием, лимит 100 МБ), удаление и редактирование своих сообщений, WebSocket-доставка, пиксель-арт фронтенд. Весь стек поднимается одной командой `docker compose up -d`.

`README.md` — описание стека, структуры и запуска (для пользователей). Требования и статус фич ведутся здесь, в разделе ниже.

## Функциональные требования и их статус

- Заход без регистрации — **готово**: вход по **email** (без пароля) + опциональный никнейм `анон-<число>`. Идентичность — по email: повторный вход с тем же email выдаёт существующую запись (тот же token), независимо от введённого никнейма; все сообщения/действия крепятся к этому id. Email хранится lowercase, unique (nullable — у записей до миграции его нет).
- Общая лента сообщений — **готово** (REST + WebSocket).
- Текст, эмодзи — **готово**.
- Файлы: фото/аудио/видео до 100 МБ — **готово**: presigned-загрузка напрямую в MinIO через прокси Vite, превью фото с полноэкранным просмотром, аудио/видео проигрываются в чате, всё скачивается.
- Лайки/дизлайки — **готово**.
- Ответы и цитирование (всего/части) — **готово**; ответы отображаются **тредами** (как комментарии под исходным сообщением, вложенность любой глубины — ответ на ответ крепится к своему родителю); если в треде больше 2 сообщений, видны корень и первый ответ, остальное — за кнопкой «▸ … ещё N» (по умолчанию все треды свёрнуты; разворачиваются кнопкой или переходом по уведомлению, сворачиваются обратно кнопкой «▾ свернуть»; у вложенных узлов правило — больше 2 прямых ответов).
- Уведомления — **готово**: об ответах (автору сообщения и всем участникам ветки) и об оценках (лайк/дизлайк — автору сообщения, «<ник> оценил сообщение 👍/👎»; снятие/смена реакции убирает уведомление, дублей нет). Колокольчик в шапке (слева от никнейма) с числом непрочитанных, выпадающий список (новые сверху), клик по уведомлению — переход к сообщению в ленте с раскрытием всего треда (догрузка истории, подсветка) + пометка прочитанным.
- Удаление и редактирование своих сообщений (текст и вложения) — **готово**; метка «изм.» (`messages.edited_at`), WS-события `message.updated`/`message.deleted`.
- Личные сообщения (1-на-1) — **готово**: кнопка «✉ в лс» у чужого сообщения создаёт/открывает диалог; отдельный экран со списком диалогов и плоской лентой (без тредов и цитат; реакции, редактирование, удаление, вложения работают); непрочитанные — `conversation_members.last_read_message_id`, бейдж на кнопке «✉» в шапке и у диалогов в списке; пометка прочитанным — при открытии диалога и при получении сообщения в открытый диалог. Приватность: личка не попадает в общую ленту, WS-события диалога (`dm.new`/`dm.updated`/`dm.deleted`/`dm.reaction`) уходят только его участникам (WS-подключение с токеном), вложения диалогов требуют `?token=` участника.
- Поиск по сообщениям — **готово**: строка поиска в шапке; ищет по общему чату и своим личным диалогам с учётом русской морфологии («приготовленное» находит «приготовление», «приготовливаю», «готовлю»); клик по результату — переход к сообщению (в ленте — догрузка истории, раскрытие треда, подсветка; в личке — открытие диалога с подсветкой).
- Антиспам — не выбран, отложено.
- Пиксель-арт интерфейс — **готово** (React + CSS, шрифты Press Start 2P / VT323).
- Автохэштеги — отложено. «Читать ветку» — отложено (задел: `messages.reply_to_id`).

## Принятые архитектурные решения

- **Бэкенд:** FastAPI (async) + Uvicorn. **ORM/миграции:** SQLAlchemy 2.0 + asyncpg + Alembic. **Конфигурация:** pydantic-settings (.env, шаблон `.env.example`).
- **Файлы (S3/MinIO):**
  - `POST /api/uploads/presign` — создаёт `Attachment` (message_id NULL) и возвращает presigned PUT URL (15 мин); бэкенд файлы не проксирует;
  - presigned URL подписываются на внутреннем endpoint (`minio:9000`), а в выдачу отдаются **относительными** (`/chatanon/<key>?X-Amz-...`, режим включается любым непустым `S3_PROXY_BASE_URL`) — браузер резолвит их от origin открытой страницы, Vite проксирует `/chatanon/*` на MinIO (`changeOrigin` ставит Host minio:9000, подпись s3v4 валидна). Медиа работают с любого устройства, открывшего страницу (localhost, телефон по Wi-Fi), CORS отсутствует. Важно: ходить нужно через origin фронтенда (5173) — при прямом запросе к бэкенду (8000) относительный редирект `/chatanon/*` упрётся в сам бэкенд и даст 404;
  - `GET /api/attachments/{id}/file` — 307 на presigned GET (12 ч); `?download=true` — Content-Disposition: attachment (filename* для не-ASCII имён); вложение сообщения из личного диалога требует `?token=` участника диалога (у `<img>` нет заголовков; чужому — 404, без токена — 401);
  - валидация: MIME image|audio|video, расширение из белого списка, размер ≤ 100 МБ (иначе 415/422).
- **БД:** PostgreSQL 17 (+ расширение `pg_trgm` для поиска). Таблицы: `participants` (есть `email`, unique), `messages` (есть `edited_at`, `conversation_id` nullable — NULL = общий чат), `attachments` (message_id nullable), `reactions`, `notifications` (participant_token + message_id, `kind` reply|like|dislike, `actor_token`, is_read), `conversations` + `conversation_members` (participant_token, `last_read_message_id` — для непрочитанных в личке). Счётчики лайков — column_property.
- **API ядра:**
  - `POST /api/participants` — тело `{email, nickname?}`: email уже есть → 200 и существующая запись (непустой никнейм обновляется), нет → 201 и новая (ник или `анон-<число>`); `GET/PATCH /api/participants/me`, заголовок `X-Participant-Token`;
  - `POST /api/messages` (текст ≤4000, reply/quote, `attachment_ids`), `GET /api/messages?before_id=&limit=` — страница **корневых** сообщений общего чата (`conversation_id IS NULL`, личка исключена; пагинация только по корням, `next_cursor`); у каждого корня поле `replies` — все потомки ветки плоским списком по id ASC (опциональный токен → `my_reaction` и у корней, и у ответов); фронт строит дерево по `reply_to_id`;
  - `PATCH /api/messages/{id}` — редактирование своего сообщения (только автор): текст + полный желаемый набор вложений; убранные файлы чистятся из S3 фоновой задачей; WS-событие `message.updated`;
  - `DELETE /api/messages/{id}` — только автор; реакции и вложения каскадом, файлы из S3 чистятся фоновой задачей, ответы сохраняются (reply_to_id → NULL); WS-событие `message.deleted`;
  - `POST /api/messages/{id}/reactions`, `DELETE /api/messages/{id}/reactions/me` — постановка оценки создаёт уведомление автору сообщения (kind=like|dislike, без дублей), снятие/смена оценки его удаляет;
  - `GET /api/notifications` (все, новые первыми), `POST /api/notifications/{id}/read` (пометка по клику); создаются при ответе для всех авторов ветки, кроме автора ответа, и при оценке — для автора сообщения (`services/notifications.py`);
  - личка: `POST /api/conversations` (найти/создать диалог с participant_token; себе — 400), `GET /api/conversations` (собеседник, последнее сообщение, unread_count; свежие сверху), `GET/POST /api/conversations/{id}/messages` (пагинация как в общей ленте; текст ≤4000, attachment_ids), `POST /api/conversations/{id}/read`; все эндпоинты — только участникам диалога (чужому 404). Уведомления в `notifications` по личке не создаются — только счётчик непрочитанных;
  - поиск: `GET /api/search/messages?q=&limit=` — по общему чату и своим диалогам (чужая личка исключена). Два слоя: FTS `to_tsvector('russian')` (словоформы одного корня) + триграммы pg_trgm (приставочные варианты: «готовлю» ↔ «приготовленное»). SQL отбирает кандидатов (FTS + свободный порог word_similarity 0.15), финальный фильтр в коде — доля общих контентных триграмм ≥ 0.6 от короткого слова пары (у pg_trgm пробельное дополнение слов даёт шум на коротких словах: «борщ» ~ «болтать»). Расширение pg_trgm + GIN-индекс по lower(text) — миграция `d41f7c2a9e05`;
  - WS `/ws/chat` (query-параметр `token` связывает сокет с участником; невалидный токен — анонимное подключение): broadcast-события `message.new`, `message.updated`, `message.deleted`, `message.reaction`, `notification.new` (в payload есть `recipient_token` — канал общий, клиент фильтрует свои); таргетированные участникам диалога — `dm.new`, `dm.updated`, `dm.deleted`, `dm.reaction` (в payload есть `conversation_id`; для сообщений с conversation_id общий broadcast НЕ делается); менеджер подключений в памяти; клиент шлёт пульс `{event:"ping"}` раз в 10 с.
- **Фронтенд:** React 18 + TS + Vite (dev-сервер в compose, прокси `/api`, `/ws`, `/chatanon` → backend/minio). Состояние — hooks. Экраны: общая лента / список диалогов / диалог (стейт `dmView` в App.tsx; личка — `components/DirectMessages.tsx`: `DmList` + `DmChat`, переиспользуют `MessageItem` без reply/quote и `Composer`; WS-события диалога App маршрутизирует в открытый `DmChat` через `registerHandler`). Общая логика черновиков вложений — `src/uploads.tsx` (`useUploads`, `DraftsView`), используется композером и редактором сообщения. Стили — чистый CSS, пиксель-арт (фото/видео — `image-rendering: auto`).
- **Архитектура:** монолит; миграции/бэкенд/фронтенд внутри docker-сети.

## Текущая структура репозитория

```
chat-anon/
├── README.md           # концепт и требования (на русском)
├── AGENTS.md           # этот файл
├── requirements.txt    # зависимости Python
├── docker-compose.yml  # postgres, minio, backend, frontend
├── docker-compose_local-repo.yml  # вариант для корп. сети: сборка через Nexus (самодостаточен, include основного)
├── .env.example
├── .gitignore
├── .dockerignore
├── backend/
│   ├── Dockerfile
│   ├── Dockerfile_local-repo  # pip из Nexus вместо pypi.org (корп. сеть)
│   ├── alembic.ini
│   ├── alembic/        # миграции (env.py на async-движок)
│   └── app/
│       ├── main.py     # FastAPI, lifespan (ensure_bucket), роутеры
│       ├── config.py   # pydantic-settings
│       ├── db.py
│       ├── models/     # participant, message, attachment, reaction, conversation (+member)
│       ├── schemas/    # pydantic-схемы (messages, conversations, notifications, participants)
│       ├── api/        # participants, messages, conversations, notifications, search, uploads, ws; deps.py
│       ├── services/   # бизнес-логика сообщений/реакций/уведомлений/диалогов
│       ├── storage/    # s3.py: presign upload/download, ensure_bucket, delete_object
│       └── ws/         # менеджер WebSocket-подключений
└── frontend/
    ├── Dockerfile      # node:20-alpine, Vite dev; npm ci из registry.npmjs.org
    ├── Dockerfile_local-repo  # npm через Nexus вместо npmjs (корп. сеть)
    ├── package.json
    ├── index.html
    ├── vite.config.ts  # прокси /api, /ws, /chatanon
    └── src/
        ├── App.tsx
        ├── api.ts      # REST-клиент, uploadFile (presign+PUT), attachmentUrl (+?token=)
        ├── uploads.tsx # useUploads (черновики вложений с загрузкой), DraftsView
        ├── ws.ts       # WS с ?token= для таргетированных событий лички
        ├── styles.css
        └── components/ # StartScreen, ChatHeader (поиск + колокольчик + ✉), MessageItem (вложения+модалка+редактор+«✉ в лс»), Composer, DirectMessages (DmList, DmChat)
```

Тестовые медиа-файлы лежат в `test-media-files/` (jpeg, mp3, mp4 с кириллическими именами) — удобны для ручных проверок.

## Сборка, запуск и тестирование

Хост — Linux; виртуальное окружение Python на хосте не требуется, весь стек в Docker.

1. Весь стек: `docker compose up -d --build` (первый раз; дальше `docker compose up -d`).
   Точка входа: **http://localhost:5173**; с телефона по Wi-Fi — **http://<IP-компа>:5173**
   (Vite слушает 0.0.0.0, все ссылки относительные; проверить, что файрвол пропускает порт 5173).
   Вариант для корпоративной сети с Nexus (pip/npm из локальных репозиториев):
   `docker compose -f docker-compose_local-repo.yml up -d --build`
   (файл самодостаточен — подключает основной через `include`; сборка переключается на
   `Dockerfile_local-repo`; двухфайловая форма `-f docker-compose.yml -f docker-compose_local-repo.yml`
   даёт тот же результат; нужен Docker Compose >= 2.20; официальный вариант — основной).
2. Миграции: `docker compose run --rm backend alembic upgrade head`;
   новая: `docker compose run --rm backend alembic revision --autogenerate -m "<описание>"`.
   Важно: правка моделей без применённой миграции роняет API (код ждёт колонку, которой нет в БД) — после изменения моделей миграцию создавать и применять сразу.
3. Код бэкенда меняется без пересборки (volume): `docker compose restart backend`. Фронтенд — hot reload, но после массовых правок надёжнее `docker compose restart frontend` (сброс кэша модулей Vite).
4. Typecheck фронта (с хоста): `cd frontend && npx tsc --noEmit`.
5. Тестов нет; проверка — smoke-сценарии. MinIO-ноги (PUT/GET к 9000) на текущем Linux-хосте работают и через асинхронный httpx, и через curl (старое зависание async httpx было спецификой Windows-связки proactor/asyncio + Docker Desktop).

## Особенности текущей сети/окружения (важно!)

- Хост — **Linux**, обычное интернет-соединение без корпоративной TLS-инспекции; зависимости скачиваются из **официальных источников**: pip — с pypi.org, npm — с registry.npmjs.org (`npm ci` по package-lock.json), образы — с Docker Hub. Для корпоративной сети с Nexus сохранён отдельный вариант запуска: `Dockerfile_local-repo` (backend/frontend) + `docker-compose_local-repo.yml` (см. «Сборка, запуск и тестирование»).
- Подключение к PostgreSQL с хоста работает (порт **5433**); миграции по-прежнему удобно гонять внутри docker-сети: `docker compose run --rm backend alembic upgrade head`.
- **MinIO не отдаёт CORS-заголовков и не отвечает на preflight** — поэтому presigned URL выдаются относительными и проксируются Vite (`/chatanon` → `minio:9000`, changeOrigin; имя бакета должно совпадать с S3_BUCKET).
- Официальные образы `minio/*` убраны с Docker Hub — используется `bitnamilegacy/minio` (для прода — `quay.io/minio/minio`).
- Периодические перезагрузки страницы чата — следить за консолью браузера (F12); на данный момент устранены пульсами WebSocket (см. `main.tsx` и `ws.ts`).

## Язык и соглашения

- Документация и комментарии — на **русском**.
- Зависимости: Python — `requirements.txt`; Node — `frontend/package.json` + `package-lock.json`.
- Обновляйте этот `AGENTS.md` по мере принятия решений.

## Вопросы, требующие проработки (явно отмечены в README)

1. Антиспам-защита — не выбрана, отложено.
2. Автоматическое присвоение хэштегов — отложено.
3. «Читать ветку» — не специфицировано; задел: `messages.reply_to_id`.
