CREATE TABLE IF NOT EXISTS element_types (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    weight      FLOAT DEFAULT 1.0,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS videos (
    id           SERIAL PRIMARY KEY,
    filename     VARCHAR(255) NOT NULL,
    filepath     TEXT NOT NULL,
    uploaded_at  TIMESTAMP DEFAULT NOW(),
    file_size    BIGINT,
    status       VARCHAR(50) DEFAULT 'uploaded'
);

CREATE TABLE IF NOT EXISTS processing_runs (
    id               SERIAL PRIMARY KEY,
    video_id         INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    status           VARCHAR(50) DEFAULT 'pending',
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP,
    config           JSONB,
    error_message    TEXT
);

CREATE TABLE IF NOT EXISTS detected_elements (
    id                 SERIAL PRIMARY KEY,
    processing_run_id  INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
    element_type_id    INTEGER REFERENCES element_types(id),
    frame_number       INTEGER,
    confidence         FLOAT,
    bounding_box       JSONB,
    metadata           JSONB,
    detected_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS progress_reports (
    id                 SERIAL PRIMARY KEY,
    processing_run_id  INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
    overall_score      FLOAT,
    section_scores     JSONB,
    element_scores     JSONB,
    generated_at       TIMESTAMP DEFAULT NOW()
);
