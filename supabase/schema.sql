-- =============================================================================
-- Herald — Telegram Delivery Layer Schema
-- =============================================================================
-- Standalone, idempotent schema for the Herald bot.
--
-- DEPENDENCY: this script assumes the master schema (../../supabase/schema.sql)
-- has already been applied so the `posts(id)` table exists. Every Herald
-- table FK-references `posts.id`.
--
-- Run order on a fresh project:
--   1. psql "$SUPABASE_DB_URL" -f supabase/schema.sql           # master
--   2. psql "$SUPABASE_DB_URL" -f herald/supabase/schema.sql    # this file
--
-- All four tables here are service_role-only via RLS — Herald is the
-- exclusive writer. Web/mobile clients have no read or write access.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. ENUM types
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
            'digest',
            'external_chat'
        );
    END IF;

    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'telegram_delivery_kind')
       AND NOT EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'telegram_delivery_kind'
              AND e.enumlabel = 'external_chat'
       ) THEN
        ALTER TYPE telegram_delivery_kind ADD VALUE 'external_chat';
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

CREATE INDEX IF NOT EXISTS idx_tg_users_last_active   ON telegram_users (last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_users_notif_mode    ON telegram_users (notif_mode);
CREATE INDEX IF NOT EXISTS idx_tg_users_not_blocked   ON telegram_users (is_blocked) WHERE is_blocked = FALSE;


-- Single source of truth for "did Herald send this post to this chat?".
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

CREATE INDEX IF NOT EXISTS idx_tg_deliveries_post     ON telegram_deliveries (post_id);
CREATE INDEX IF NOT EXISTS idx_tg_deliveries_chat     ON telegram_deliveries (chat_id);
CREATE INDEX IF NOT EXISTS idx_tg_deliveries_sent_at  ON telegram_deliveries (sent_at DESC);


-- Per-user bookmarks set via inline keyboard.
CREATE TABLE IF NOT EXISTS telegram_bookmarks (
    tg_user_id   BIGINT       NOT NULL REFERENCES telegram_users(tg_user_id) ON DELETE CASCADE,
    post_id      UUID         NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    saved_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tg_user_id, post_id)
);

CREATE INDEX IF NOT EXISTS idx_tg_bookmarks_user ON telegram_bookmarks (tg_user_id, saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_bookmarks_post ON telegram_bookmarks (post_id);


-- Groups, supergroups and channels where users have added the Herald bot.
-- Each active row receives every newly published post via ChatFanout.
CREATE TABLE IF NOT EXISTS telegram_subscribed_chats (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tg_chat_id        BIGINT       NOT NULL UNIQUE,
    chat_type         TEXT         NOT NULL,
    title             TEXT,
    username          TEXT,
    added_by_user_id  BIGINT,
    muted_categories  TEXT[]       NOT NULL DEFAULT '{}',
    min_score         INT          NOT NULL DEFAULT 0,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    added_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    removed_at        TIMESTAMPTZ,
    last_post_at      TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tg_chats_active   ON telegram_subscribed_chats (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_tg_chats_type     ON telegram_subscribed_chats (chat_type);
CREATE INDEX IF NOT EXISTS idx_tg_chats_added_at ON telegram_subscribed_chats (added_at DESC);


-- Native Telegram message reactions, harvested for the website's
-- "trending" signal.
CREATE TABLE IF NOT EXISTS telegram_reactions (
    post_id      UUID         NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tg_user_id   BIGINT       NOT NULL,
    reaction     TEXT         NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, tg_user_id, reaction)
);

CREATE INDEX IF NOT EXISTS idx_tg_reactions_post     ON telegram_reactions (post_id);
CREATE INDEX IF NOT EXISTS idx_tg_reactions_recent   ON telegram_reactions (created_at DESC);


-- ---------------------------------------------------------------------------
-- 3. Row Level Security — service role only.
-- ---------------------------------------------------------------------------
ALTER TABLE telegram_users             ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_deliveries        ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_bookmarks         ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_reactions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_subscribed_chats  ENABLE ROW LEVEL SECURITY;

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

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='telegram_subscribed_chats'
          AND policyname='Telegram subscribed chats service role only'
    ) THEN
        CREATE POLICY "Telegram subscribed chats service role only"
            ON telegram_subscribed_chats FOR ALL USING (false);
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 4. Grants
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_users      TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_deliveries TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_bookmarks  TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_reactions         TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_subscribed_chats   TO service_role;
GRANT USAGE, SELECT ON SEQUENCE telegram_deliveries_id_seq          TO service_role;


-- ---------------------------------------------------------------------------
-- 5. Realtime — publish telegram_deliveries so multi-instance Herald
--    deployments can coordinate without polling.
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
-- 6. Convenience view — posts awaiting Telegram channel delivery.
--    Used by Herald's safety-net poller as a fast O(1) lookup.
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
