-- Migration 002: Add combo intelligence columns to menu_combos
-- Idempotent — safe to re-run.

ALTER TABLE menu_combos
  ADD COLUMN IF NOT EXISTS combo_size  INT             DEFAULT 2,
  ADD COLUMN IF NOT EXISTS combo_score NUMERIC(8,4)    DEFAULT 0,
  ADD COLUMN IF NOT EXISTS lift        NUMERIC(8,4)    DEFAULT 1;

-- Index for fast leaderboard queries
CREATE INDEX IF NOT EXISTS idx_menu_combos_score
  ON menu_combos (combo_score DESC, combo_size DESC, combo_id ASC)
  WHERE is_active = TRUE;
