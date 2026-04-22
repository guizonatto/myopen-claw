
FROM ghcr.io/openclaw/openclaw:latest

USER root

# Install Docker CLI at build time (was runtime apt-get in entrypoint.sh)
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends docker.io curl git \
    && rm -rf /var/lib/apt/lists/*

COPY ./openclaw.json /opt/openclaw-bootstrap/openclaw.json
COPY ./skills/       /opt/openclaw-bootstrap/workspace/skills/
COPY ./configs/      /opt/openclaw-bootstrap/workspace/configs/
COPY ./crons/        /opt/openclaw-bootstrap/workspace/crons/
COPY ./scripts/      /opt/openclaw-bootstrap/workspace/scripts/
COPY ./hooks/        /opt/openclaw-bootstrap/hooks/

# Extract and install MemClaw at build time (was runtime npm install in entrypoint.sh)
COPY ./memclaw-memclaw-0.9.39.tgz /opt/openclaw-bootstrap/memclaw.tgz
RUN mkdir -p /opt/openclaw-bootstrap/extensions/memclaw \
    && tar -xzf /opt/openclaw-bootstrap/memclaw.tgz \
        -C /opt/openclaw-bootstrap/extensions/memclaw --strip-components=1 \
    && cd /opt/openclaw-bootstrap/extensions/memclaw \
    && npm install --omit=dev

COPY requirements.txt /app/requirements.txt

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

EXPOSE 18789

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
