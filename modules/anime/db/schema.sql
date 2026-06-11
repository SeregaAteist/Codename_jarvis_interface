-- Anime-модуль (Фаза 14). БД отдельно от jarvis.db: data/sqlite/anime.db.

-- Тайтлы
CREATE TABLE IF NOT EXISTS titles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    animevost_id INTEGER UNIQUE,
    shikimori_id INTEGER,
    title_ru TEXT NOT NULL,
    title_en TEXT,
    title_original TEXT,
    description_ru TEXT,
    description_en TEXT,
    description_original TEXT,
    poster_url TEXT,
    genres TEXT,              -- JSON array
    status TEXT,              -- ongoing / completed / announced
    episodes_total INTEGER,
    episodes_aired INTEGER,
    seasons INTEGER DEFAULT 1,
    specials INTEGER DEFAULT 0,
    rating_animevost REAL,
    rating_shikimori REAL,
    year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Серии
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id INTEGER REFERENCES titles(id),
    season INTEGER DEFAULT 1,
    episode_number INTEGER,
    episode_name TEXT,
    description TEXT,
    rating REAL,
    air_date TIMESTAMP,
    url TEXT,
    notified_at TIMESTAMP,    -- NULL = ещё не уведомляли
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Вотч-лист
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id INTEGER REFERENCES titles(id),
    status TEXT NOT NULL,     -- watching / completed / planned / dropped / on_hold
    episodes_watched INTEGER DEFAULT 0,
    score INTEGER,            -- личная оценка 1-10
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shikimori sync лог
CREATE TABLE IF NOT EXISTS shikimori_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    titles_added INTEGER DEFAULT 0,
    titles_updated INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_episodes_title ON episodes(title_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_status ON watchlist(status);
