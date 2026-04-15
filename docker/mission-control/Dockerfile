FROM node:20-bookworm-slim AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS fetcher
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl tar ca-certificates \
  && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/crshdn/mission-control/archive/refs/heads/main.tar.gz \
  | tar -xz --strip-components=1

FROM base AS build-deps
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 make g++ \
  && rm -rf /var/lib/apt/lists/*
COPY --from=fetcher /app/package*.json ./
RUN npm ci

FROM base AS prod-deps
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 make g++ \
  && rm -rf /var/lib/apt/lists/*
COPY --from=fetcher /app/package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

FROM base AS builder
COPY --from=build-deps /app/node_modules ./node_modules
COPY --from=fetcher /app .
# Patch: normaliza model para string quando gateway retorna {primary: "..."}
RUN sed -i 's/model: e\.model,/model: typeof e.model === "object" \&\& e.model !== null ? ((e.model as any).primary || JSON.stringify(e.model)) : e.model,/g' \
    src/app/api/agents/discover/route.ts || true
RUN npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
  NEXT_TELEMETRY_DISABLED=1 \
  PORT=4000 \
  DATABASE_PATH=/app/data/mission-control.db \
  WORKSPACE_BASE_PATH=/app/workspace \
  PROJECTS_PATH=/app/workspace/projects

RUN apt-get update \
  && apt-get install -y --no-install-recommends dumb-init \
  && rm -rf /var/lib/apt/lists/*

COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./next.config.mjs

RUN mkdir -p /app/data /app/workspace/projects \
  && chown -R node:node /app

USER node
EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:4000/api/events').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

ENTRYPOINT ["dumb-init", "--"]
CMD ["npm", "run", "start"]
