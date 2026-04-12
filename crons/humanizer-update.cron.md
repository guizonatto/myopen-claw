openclaw cron add \
  --name "humanizer-wikipedia-sync" \
  --cron "0 6 * * 1" \
  --session isolated \
  --agent default \
  --message "humanizer self-update" \
  --timezone "America/Sao_Paulo"
