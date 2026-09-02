FROM node:22.19-alpine AS build

WORKDIR /app

COPY services/proxy-hub/frontend/package.json ./
COPY services/proxy-hub/frontend/package-lock.json ./
RUN npm ci

COPY services/proxy-hub/frontend/index.html ./
COPY services/proxy-hub/frontend/tsconfig.json ./
COPY services/proxy-hub/frontend/tsconfig.app.json ./
COPY services/proxy-hub/frontend/tsconfig.node.json ./
COPY services/proxy-hub/frontend/vite.config.ts ./
COPY services/proxy-hub/frontend/src ./src

RUN npm run build

FROM nginx:1.27-alpine

COPY infra/proxy-hub/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html/console

EXPOSE 8080
