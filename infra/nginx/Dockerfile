# Stage 1: Build UI
FROM node:20-slim AS ui-build
WORKDIR /build
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ .
RUN npx vite build

# Stage 2: Nginx
FROM nginx:alpine
COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=ui-build /build/dist/public /usr/share/nginx/html
