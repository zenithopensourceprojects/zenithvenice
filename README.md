# Herald

The Telegram delivery layer for **India Verified**. Reads verified posts from
Supabase the moment they are published and broadcasts them to a Telegram
forum supergroup, one topic per category. Includes an interactive bot for
on-demand browsing and search.

```
RSS / scrapers → worker → supabase.posts ─┬─ frontend (Next.js)
                                          └─ herald   (this package)
```

## What it does

- Listens to Supabase realtime on `posts` for instant push to Telegram
- 60-second safety-net poller against `posts_pending_channel_delivery` view
- Token-bucket rate limiter (Telegram allows 30 msg/s global, 1 msg/s per chat)
- Renders each post as a polished HTML card with credibility score, source
  list, and a native first-source link preview
- Inline buttons: **Read full**, **All sources**, **Save**, **Share**
- Bot commands: `/start`, `/latest`, `/categories`, `/search`, `/about`,
  `/help`
- Idempotent deliveries via the `telegram_deliveries` unique constraint

## Stack

- Python 3.11+
- [`aiogram`](https://docs.aiogram.dev/) 3.x — async Telegram bot framework
- [`supabase-py`](https://github.com/supabase/supabase-py) 2.x — Supabase client
- [`pydantic`](https://docs.pydantic.dev/) 2.x — settings + model validation
- [`structlog`](https://www.structlog.org/) — JSON logs in prod, pretty in dev

## Quick start (dev)

```bash
cd herald
cp example.env .env
# edit .env with your bot token, channel id, supabase keys, topic ids

pip install -e .
python -m herald
```

## Database

Herald requires migration `006_telegram_integration.sql` to be applied. It
adds four tables (`telegram_users`, `telegram_deliveries`,
`telegram_bookmarks`, `telegram_reactions`), two enum types, RLS policies,
realtime publication, and a `posts_pending_channel_delivery` view.

```bash
psql "$SUPABASE_DB_URL" -f ../supabase/migrations/006_telegram_integration.sql
```

## Layout

```
herald/
├── src/herald/
│   ├── main.py                  entrypoint
│   ├── config.py                pydantic Settings
│   ├── logging_setup.py
│   ├── utils/                   hostname, time_ago, html escape
│   ├── data/                    supabase client + queries + pydantic models
│   ├── render/                  card / credibility / sources / bullets
│   ├── bot/                     aiogram handlers
│   │   ├── dispatcher.py
│   │   ├── keyboards.py
│   │   ├── callbacks.py
│   │   └── commands/
│   └── publisher/
│       ├── scheduler.py         token-bucket rate limiter
│       ├── dispatch.py          idempotent send
│       ├── poller.py            60s safety net
│       └── realtime.py          supabase realtime listener
├── tests/
└── deploy/
    └── systemd/herald.service
```

## Deploy

### Docker

```bash
docker build -t herald .
docker run --env-file .env herald
```

### systemd (VPS)

```bash
sudo cp deploy/systemd/herald.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now herald
sudo journalctl -fu herald
```

## License

Same as the parent project.
