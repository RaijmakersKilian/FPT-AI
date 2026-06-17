-- =============================================================
-- FPT AI  –  Database schema
-- Run this in Supabase: SQL Editor → New query → Run
-- Safe to re-run: every statement uses IF NOT EXISTS / OR REPLACE
-- =============================================================

-- UUID helper (already enabled on Supabase, just in case)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- -------------------------------------------------------------
-- 1. element_type
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS element_type (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    color_hex   VARCHAR(7)          -- e.g. #FF5733
);


-- -------------------------------------------------------------
-- 2. video
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS video (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename         VARCHAR(255)    NOT NULL,
    file_path        TEXT            NOT NULL,   -- Supabase Storage public URL
    duration_seconds INTEGER,
    total_frames     INTEGER,
    file_size_mb     NUMERIC(10, 2),
    uploaded_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    notes            TEXT
);


-- -------------------------------------------------------------
-- 3. processing_run
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processing_run (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id         UUID REFERENCES video(id) ON DELETE CASCADE,
    element_type_id  UUID REFERENCES element_type(id) ON DELETE SET NULL,
    status           VARCHAR(20)     NOT NULL DEFAULT 'pending',
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    frames_extracted INTEGER,
    pointcloud_path  TEXT,
    detections_path  TEXT,
    bim_model_path   TEXT
);


-- -------------------------------------------------------------
-- 4. detected_element
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detected_element (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID            NOT NULL REFERENCES processing_run(id) ON DELETE CASCADE,
    element_type_id  UUID            NOT NULL REFERENCES element_type(id)   ON DELETE CASCADE,
    frame_id         INTEGER         NOT NULL,
    confidence       NUMERIC(6, 4),
    bbox_x1          NUMERIC,
    bbox_y1          NUMERIC,
    bbox_x2          NUMERIC,
    bbox_y2          NUMERIC,
    mask_polygon     JSONB,
    depth_estimate_m NUMERIC,
    detected_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- -------------------------------------------------------------
-- 5. progress_report
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS progress_report (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID            NOT NULL REFERENCES processing_run(id) ON DELETE CASCADE,
    element_type_id  UUID            NOT NULL REFERENCES element_type(id)   ON DELETE CASCADE,
    total_elements   INTEGER         NOT NULL DEFAULT 0,
    completed        INTEGER         NOT NULL DEFAULT 0,
    partial          INTEGER         NOT NULL DEFAULT 0,
    not_built        INTEGER         NOT NULL DEFAULT 0,
    completion_pct   NUMERIC(5, 2),
    current_stage    TEXT,
    pdf_path         TEXT,
    csv_path         TEXT,
    generated_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- If the table already existed before this script, run this once in Supabase SQL Editor:
--   ALTER TABLE progress_report ADD COLUMN IF NOT EXISTS csv_path TEXT;
