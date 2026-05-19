-- =============================================================================
-- 006_telegram_integration
-- Adds the Telegram delivery layer (Herald bot).
-- Reuses the existing `posts` table; introduces 4 new tables for users,
-- deliveries, bookmarks, and reactions. Idempotent.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. ENUM types (created via DO blocks for idempotency)
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'telegram_notif_mode') THEN
        CREATE TYPE telegram_notif_mode AS ENUM (
            'instant',
            'digest',
            'breaking_only',
            'silent'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'telegram_delivery_kind') THEN
        CREATE TYPE telegram_delivery_kind AS ENUM (
            'channel',
            'user_alert',
            'digest'
        );
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 2. Tables
-- ---------------------------------------------------------------------------

-- Telegram users who have started the Herald bot in DM.
CREATE TABLE IF NOT EXISTS telegram_users (
    tg_user_id            BIGINT       PRIMARY KEY,
    tg_chat_id            BIGINT       NOT NULL,
    username              TEXT,
    first_name            TEXT,
    language_code         TEXT         NOT NULL DEFAULT 'en',
    timezone              TEXT         NOT NULL DEFAULT 'Asia/Kolkata',
    subscribed_categories TEXT[]       NOT NULL DEFAULT '{}',
    muted_categories      TEXT[]       NOT NULL DEFAULT '{}',
    notif_mode            telegram_notif_mode NOT NULL DEFAULT 'instant',
    quiet_start           TIME         NOT NULL DEFAULT '23:00',
    quiet_end             TIME         NOT NULL DEFAULT '07:00',
    is_blocked            BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_active_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tg_users_last_active   ON telegram_users(last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_users_notif_mode    ON telegram_users(notif_mode);
CREATE INDEX IF NOT EXISTS idx_tg_users_not_blocked   ON telegram_users(is_blocked) WHERE is_blocked = FALSE;


-- Single source of truth for "did Herald send this post to this chat?"
-- Prevents duplicate deliveries on realtime + poller race conditions.
CREATE TABLE IF NOT EXISTS telegram_deliveries (
    id           BIGSERIAL    PRIMARY KEY,
    post_id      UUID         NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    chat_id      BIGINT       NOT NULL,
    topic_id     BIGINT,
    message_id   BIGINT       NOT NULL,
    kind         telegram_delivery_kind NOT NULL,
    sent_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (post_id, chat_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_tg_deliveries_post     ON telegram_deliveries(post_id);
CREATE INDEX IF NOT EXISTS idx_tg_deliveries_chat     ON telegram_deliveries(chat_id);
CREATE INDEX IF NOT EXISTS idx_tg_deliveries_sent_at  ON telegram_deliveries(sent_at DESC);


-- Per-user bookmarks set via inline keyboard.
CREATE TABLE IF NOT EXISTS telegram_bookmarks (
    tg_user_id   BIGINT       NOT NULL REFERENCES telegram_users(tg_user_id) ON DELETE CASCADE,
    post_id      UUID         NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    saved_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tg_user_id, post_id)
);

CREATE INDEX IF NOT EXISTS idx_tg_bookmarks_user ON telegram_bookmarks(tg_user_id, saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_bookmarks_post ON telegram_bookmarks(post_id);


-- Native Telegram message reactions (👍 ❤️ 🔥 ...) collected for
-- "trending" signals on the website.
CREATE TABLE IF NOT EXISTS telegram_reactions (
    post_id      UUID         NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tg_user_id   BIGINT       NOT NULL,
    reaction     TEXT         NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, tg_user_id, reaction)
);

CREATE INDEX IF NOT EXISTS idx_tg_reactions_post     ON telegram_reactions(post_id);
CREATE INDEX IF NOT EXISTS idx_tg_reactions_recent   ON telegram_reactions(created_at DESC);


-- ---------------------------------------------------------------------------
-- 3. Row Level Security
-- All Telegram tables are service_role only — Herald is the only writer.
-- ---------------------------------------------------------------------------
ALTER TABLE telegram_users      ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_bookmarks  ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_reactions  ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='telegram_users'
          AND policyname='Telegram users service role only'
    ) THEN
        CREATE POLICY "Telegram users service role only"
            ON telegram_users FOR ALL USING (false);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='telegram_deliveries'
          AND policyname='Telegram deliveries service role only'
    ) THEN
        CREATE POLICY "Telegram deliveries service role only"
            ON telegram_deliveries FOR ALL USING (false);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='telegram_bookmarks'
          AND policyname='Telegram bookmarks service role only'
    ) THEN
        CREATE POLICY "Telegram bookmarks service role only"
            ON telegram_bookmarks FOR ALL USING (false);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='telegram_reactions'
          AND policyname='Telegram reactions service role only'
    ) THEN
        CREATE POLICY "Telegram reactions service role only"
            ON telegram_reactions FOR ALL USING (false);
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 4. Grants
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_users      TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_deliveries TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_bookmarks  TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_reactions  TO service_role;
GRANT USAGE, SELECT ON SEQUENCE telegram_deliveries_id_seq  TO service_role;


-- ---------------------------------------------------------------------------
-- 5. Realtime
-- Herald subscribes to INSERTs on `posts`. Already in publication via 001;
-- we additionally publish telegram_deliveries so multi-instance deployments
-- of Herald can coordinate without polling.
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_publication_tables
        WHERE pubname    = 'supabase_realtime'
          AND schemaname = 'public'
          AND tablename  = 'telegram_deliveries'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE telegram_deliveries;
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 6. Convenience view: posts awaiting Telegram channel delivery
-- Fast O(1) lookup for the safety-net poller.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW posts_pending_channel_delivery AS
SELECT p.*
FROM posts p
LEFT JOIN telegram_deliveries d
       ON d.post_id = p.id
      AND d.kind    = 'channel'
WHERE p.status = 'published'
  AND d.id IS NULL
ORDER BY p.published_at DESC;

GRANT SELECT ON posts_pending_channel_delivery TO service_role;
