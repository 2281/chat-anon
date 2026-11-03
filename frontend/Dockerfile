# Образ для локальной разработки фронтенда: Vite dev-сервер с hot reload.
# Продакшн-сборка (nginx и т.п.) — отдельным этапом, когда она понадобится.
FROM node:20-alpine

WORKDIR /app

COPY package.json ./
# npm через корпоративный Nexus (plain HTTP) — как у pip в backend.
# Прямой доступ к registry.npmjs.org внутри контейнера ломается
# корпоративной TLS-инспекцией (SELF_SIGNED_CERT_IN_CHAIN).
RUN npm config set registry http://nexus.rw.org/repository/npm/ --global
# после появления package-lock.json в репозитории заменить на: RUN npm ci
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
