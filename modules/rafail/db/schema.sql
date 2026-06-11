-- Рафаил — корпоративная база знаний LK Energy Group (rafail.db)

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT,          -- ses / energy / sales / internal
    track TEXT,           -- sales / engineers / installers / all
    source_url TEXT,
    source_type TEXT,     -- rss / web / youtube / drive / crm / ringostat
    title TEXT,
    raw_content TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER REFERENCES materials(id),
    content_type TEXT,    -- course_section / quiz / case_study / summary
    track TEXT,
    title TEXT,
    content TEXT,
    status TEXT DEFAULT 'pending', -- pending/approved/rejected/uploaded
    approved_at TIMESTAMP,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moodle_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processed_id INTEGER REFERENCES processed(id),
    moodle_course_id INTEGER,
    moodle_section_id INTEGER,
    moodle_activity_id INTEGER,
    drive_file_id TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    status TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_materials_domain ON materials(domain);
CREATE INDEX IF NOT EXISTS idx_materials_track ON materials(track);
CREATE INDEX IF NOT EXISTS idx_processed_status ON processed(status);
CREATE INDEX IF NOT EXISTS idx_moodle_map_processed ON moodle_map(processed_id);
