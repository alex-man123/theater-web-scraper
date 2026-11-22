-- Rulat automat de containerul MySQL la prima pornire (după 01-schema.sql).
-- Creează baza separată pentru testele automate și îi dă drepturi utilizatorului aplicației.
-- Dacă ați schimbat DB_USER în .env, înlocuiți 'odeon_app' mai jos.
CREATE DATABASE IF NOT EXISTS theater_crawler_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON theater_crawler_test.* TO 'odeon_app'@'%';
FLUSH PRIVILEGES;
