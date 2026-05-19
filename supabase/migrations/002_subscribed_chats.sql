-- =============================================================================
-- 002_subscribed_chats
-- Lets users add the Herald bot to their own groups, supergroups, or channels.
-- Each chat where the bot is a member with permission to post is registered
-- here and receives every newly published post via ChatFanout.
-- Idempotent.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. Extend the delivery-kind enum so external-chat sends are tracked
--    separately from the official channel and from user DMs.
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    IF NOT EXISTS (
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
-- 2. telegram_subscribed_chats
--    A row per group/supergroup/channel that has added the Herald bot.
--    Marked is_active = FALSE on kick/leave instead of being deleted so that
--    historical telegram_deliveries rows stay meaningful.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telegram_subscribed_chats (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tg_chat_id        BIGINT       NOT NULL UNIQUE,
    chat_type         TEXT         NOT NULL,    -- 'group' | 'supergroup' | 'channel'
    title             TEXT,
    username          TEXT,
    added_by_user_id  BIGINT,                   -- NULL for channels (no from_user)
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


-- ---------------------------------------------------------------------------
-- 3. Row Level Security — service role only.
-- ---------------------------------------------------------------------------
ALTER TABLE telegram_subscribed_chats ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename  = 'telegram_subscribed_chats'
          AND policyname = 'Telegram subscribed chats service role only'
    ) THEN
        CREATE POLICY "Telegram subscribed chats service role only"
            ON telegram_subscribed_chats FOR ALL USING (false);
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 4. Grants
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON telegram_subscribed_chats TO service_role;
