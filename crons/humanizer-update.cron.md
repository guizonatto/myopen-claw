openclaw cron add \
  --name "humanizer-wikipedia-sync" \
  --cron "0 6 * * 1" \
  --session isolated \
  --no-deliver \
  --agent default \
  --message "humanizer self-update" \
  --tz "${CRON_TZ:-America/Sao_Paulo}"
