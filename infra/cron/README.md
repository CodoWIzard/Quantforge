# Scheduled jobs

## Board refresh
Keeps the `#progress` embed's due-date countdown accurate.

| | |
|---|---|
| Job ID | `f9a8011fa563` |
| Schedule | `0 * * * *` (hourly) |
| Mode | `no_agent` — script only, no LLM tokens |
| Delivery | `local` (silent; CLI sessions have no delivery channel) |
| Installed at | `~/.hermes/scripts/quantforge_board_refresh.sh` |

The canonical copy lives here in the repo. `~/.hermes/scripts/` holds the
installed copy because Hermes requires cron scripts to be relative to that
directory — an absolute path is rejected.

### Behaviour
- **Success:** silent, exit 0. Nothing is sent.
- **Failure:** prints the error and exits 1, so a broken refresh is visible
  rather than failing quietly.

Both paths are tested before install.

### Commands
```bash
hermes cron list
hermes cron run f9a8011fa563       # force a run now
hermes cron pause f9a8011fa563
```

### Updating
Edit the copy in this repo, then reinstall:
```bash
cp infra/cron/quantforge_board_refresh.sh ~/.hermes/scripts/
```
