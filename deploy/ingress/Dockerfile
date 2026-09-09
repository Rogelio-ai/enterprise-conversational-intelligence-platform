FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY proxy.conf /etc/nginx/proxy.conf
RUN mkdir -p /var/cache/nginx/client_temp /var/cache/nginx/proxy_temp \
    && chown -R nginx:nginx /var/cache/nginx /var/run
USER nginx
EXPOSE 8080 8443
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD wget --no-check-certificate -qO- https://127.0.0.1:8443/health || exit 1
