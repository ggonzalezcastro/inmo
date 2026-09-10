FROM node:22-alpine AS build

WORKDIR /app

RUN npm install --global npm@12.0.2

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=https://api.captame.cl
ARG VITE_API_BASE_URL=https://api.captame.cl
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build


FROM nginx:alpine AS runtime

ENV PORT=8080
ENV NGINX_ENVSUBST_FILTER=PORT

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider "http://127.0.0.1:${PORT}/health" || exit 1
