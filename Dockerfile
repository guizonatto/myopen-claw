
FROM ghcr.io/openclaw/openclaw:latest

USER root

COPY ./openclaw.json /opt/openclaw-bootstrap/openclaw.json
COPY ./skills/       /opt/openclaw-bootstrap/workspace/skills/
COPY ./configs/      /opt/openclaw-bootstrap/workspace/configs/
COPY ./crons/        /opt/openclaw-bootstrap/workspace/crons/
COPY ./scripts/      /opt/openclaw-bootstrap/workspace/scripts/
COPY ./hooks/        /opt/openclaw-bootstrap/hooks/

# Tgz do memclaw bundled para instalação em runtime (evita npm pack no build)
COPY ./memclaw-memclaw-0.9.39.tgz /opt/openclaw-bootstrap/memclaw.tgz

COPY requirements.txt /app/requirements.txt

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

EXPOSE 18789

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
