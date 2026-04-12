FROM docker:27-cli
RUN apk add --no-cache git bash
COPY update.sh /update.sh
COPY crontab /etc/crontabs/root
RUN chmod +x /update.sh
CMD ["crond", "-f", "-l", "2"]
