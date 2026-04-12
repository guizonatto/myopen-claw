
FROM ghcr.io/openclaw/openclaw:latest

USER root

# Instala Node.js, pip e Playwright (e browsers)
RUN apt-get update && apt-get install -y --no-install-recommends nodejs python3-pip && \
    python3 -m pip install --break-system-packages playwright && \
    python3 -m playwright install --with-deps

# Corrige ownership dos plugins/extensions que a imagem base instala com uid=1000
RUN chown -R root:root /app/extensions 2>/dev/null || true

# Instala o Docker CLI para que o gateway possa usar 'docker exec' nos containers dos MCPs
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Instala o Homebrew (Linuxbrew)
RUN /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || true
ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:$PATH"

# Instala o plugin MemClaw
#RUN openclaw plugins install @memclaw/memclaw



# Copia as Skills e a configuração inicial do OpenClaw
RUN mkdir -p /root/.openclaw/workspace/skills
RUN mkdir -p /root/.openclaw/workspace/crons

COPY ./openclaw.json /root/.openclaw/openclaw.json
COPY ./skills/ /root/.openclaw/workspace/skills/
COPY ./configs/ /root/.openclaw/workspace/configs/
COPY ./crons/ /root/.openclaw/workspace/crons/
COPY ./scripts/ /root/.openclaw/workspace/scripts/
COPY ./hooks/ /root/.openclaw/hooks/

COPY requirements.txt /app/requirements.txt
RUN pip install --break-system-packages -r /app/requirements.txt

RUN echo "Skills copiadas para /root/.openclaw/workspace/skills:" && \
    ls -l /root/.openclaw/workspace/skills
RUN echo "Crons copiados para /root/.openclaw/workspace/crons:" && \
    ls -l /root/.openclaw/workspace/crons


COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 18789

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]