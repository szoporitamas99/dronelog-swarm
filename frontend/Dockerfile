# Fixed, verified release; never use :latest in the project.
FROM nginx:1.30.7-alpine3.24

LABEL org.opencontainers.image.title="DroneLog frontend" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="Hungarian drone mission dashboard and reverse proxy"

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html styles.css app.js favicon.svg /usr/share/nginx/html/

USER nginx
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1

# The official entrypoint edits /etc; this configuration needs no startup edits.
ENTRYPOINT []
CMD ["nginx", "-g", "daemon off;"]
