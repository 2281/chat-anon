# Образ для локальной разработки фронтенда: Vite dev-сервер с hot reload.
# Продакшн-сборка (nginx и т.п.) — отдельным этапом, когда она понадобится.
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
# зависимости — из официального registry.npmjs.org, строго по lock-файлу
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
