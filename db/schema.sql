-- Schema bazei de date pentru crawlerul Teatrului Odeon (MySQL 8.x).
--
-- Pornește de la scriptul din "Proiecte_Crawlere_Teatre.pdf". Toate câmpurile
-- din PDF sunt păstrate. Adaptări (permise de PDF: "Structura poate fi modificată"):
--   shows.slug          identificator natural din URL (/spectacol/<slug>/), UNIQUE ->
--                       un spectacol nu poate fi inserat de două ori
--                       (source_url e prea lung pentru un index UNIQUE în utf8mb4)
--   shows.subtitle      linia de credit publicată ("de A. P. Cehov, regia ..."), păstrată textual
--   shows.origin        'show_page' = colectat din pagina spectacolului;
--                       'schedule'  = apare doar în program, fără pagină proprie
--   performances.external_id   id-ul stabil al cardului din program (data-perf-id), UNIQUE
--   performances.source_title  titlul exact afișat în program (poate diferi de titlul spectacolului)
--
-- Baza de date se creează separat (vezi README):
--   CREATE DATABASE theater_crawler CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Toate coloanele TIMESTAMP sunt scrise în UTC (conexiunea setează time_zone='+00:00');
-- aplicația le convertește în ora României (Europe/Bucharest) la afișare.

CREATE TABLE IF NOT EXISTS shows (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    slug VARCHAR(191) NOT NULL,
    origin ENUM('show_page', 'schedule') NOT NULL DEFAULT 'show_page',

    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(500) NULL,
    author VARCHAR(255) NULL,
    director VARCHAR(255) NULL,
    description TEXT NULL,
    genre VARCHAR(255) NULL,
    language VARCHAR(255) NULL,

    duration_minutes INT UNSIGNED NULL,
    duration_text VARCHAR(255) NULL,
    age_recommendation VARCHAR(255) NULL,
    premiere_date DATE NULL,

    cast_json JSON NULL,
    team_json JSON NULL,

    poster_storage ENUM('file', 'base64') NULL,
    poster_path VARCHAR(1024) NULL,
    poster_base64 LONGTEXT NULL,
    poster_mime_type VARCHAR(100) NULL,
    poster_source_url VARCHAR(2048) NULL,
    poster_hash CHAR(64) NULL,

    source_url VARCHAR(2048) NOT NULL,
    last_seen_at TIMESTAMP NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_shows_slug (slug),
    INDEX idx_shows_title (title),
    INDEX idx_shows_author (author),
    INDEX idx_shows_director (director),
    INDEX idx_shows_premiere_date (premiere_date)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS performances (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    show_id BIGINT UNSIGNED NOT NULL,

    external_id VARCHAR(100) NULL,
    source_title VARCHAR(255) NULL,

    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NULL,
    venue VARCHAR(255) NULL,
    performance_type VARCHAR(100) NULL,
    status VARCHAR(50) NULL,
    notes TEXT NULL,

    source_url VARCHAR(2048) NULL,
    last_seen_at TIMESTAMP NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_performances_show
        FOREIGN KEY (show_id)
        REFERENCES shows(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    UNIQUE KEY uq_performances_external_id (external_id),
    INDEX idx_performances_show_id (show_id),
    INDEX idx_performances_start_at (start_at),
    INDEX idx_performances_venue (venue),
    INDEX idx_performances_show_date (show_id, start_at)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;
