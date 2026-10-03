# Build stage
FROM node:24-alpine AS builder

# pnpm needs non-interactive mode when purging node_modules (no TTY in Docker)
ENV CI=true

RUN npm install -g pnpm

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

# Production stage
FROM node:24-alpine

WORKDIR /app

COPY --from=builder /app/.output ./.output

EXPOSE 3000

# Railway injects PORT; Nuxt SSR respects it (default 3000 for local Docker)
ENV PORT=3000
ENV HOST=0.0.0.0
ENV NITRO_HOST=0.0.0.0
ENV NITRO_PORT=3000

CMD ["sh", "-c", "export NITRO_PORT=${PORT:-3000}; export PORT=${PORT:-3000}; node .output/server/index.mjs"]
