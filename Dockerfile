FROM ghcr.io/openclaw/openclaw:latest

USER root

# Instala o Docker CLI para que o gateway possa usar 'docker exec' nos containers dos MCPs
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copia as Skills e a configuração inicial do OpenClaw
RUN mkdir -p /root/.openclaw/workspace/skills

COPY ./openclaw.json /root/.openclaw/openclaw.json
COPY ./skills/ /root/.openclaw/workspace/skills/
RUN echo "Skills copiadas para /root/.openclaw/workspace/skills:" && \
    ls -l /root/.openclaw/workspace/skills


COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 18789

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]