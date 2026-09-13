FROM node:24-alpine AS build
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig*.json vite.config.ts ./
COPY src ./src
ARG VITE_DEMO_MODE=false
ENV VITE_API_BASE_URL=/api \
    VITE_PUBLIC_BASE_PATH=/staff/ \
    VITE_ROUTER_BASENAME=/staff \
    VITE_DEMO_MODE=${VITE_DEMO_MODE}
RUN npm run build

FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=nginx:nginx /build/dist /usr/share/nginx/html
RUN touch /run/nginx.pid \
    && chown -R nginx:nginx /var/cache/nginx /run/nginx.pid
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
