-- A hivatalos PostgreSQL image csak az üres adatvolume első indításakor futtatja.
-- A séma későbbi változásához külön migráció kell; a meglévő volume nem törlendő.
BEGIN;

CREATE TABLE IF NOT EXISTS missions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(120) NOT NULL CHECK (char_length(btrim(title)) BETWEEN 3 AND 120),
    location VARCHAR(120) NOT NULL CHECK (char_length(btrim(location)) BETWEEN 2 AND 120),
    aircraft VARCHAR(80) NOT NULL CHECK (char_length(btrim(aircraft)) BETWEEN 2 AND 80),
    mission_date DATE NOT NULL CHECK (mission_date BETWEEN DATE '2000-01-01' AND DATE '2100-12-31'),
    flight_minutes INTEGER NOT NULL DEFAULT 0 CHECK (flight_minutes BETWEEN 0 AND 600),
    status VARCHAR(16) NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'completed')),
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS missions_date_idx ON missions (mission_date DESC, id DESC);

INSERT INTO missions (title, location, aircraft, mission_date, flight_minutes, status, notes) VALUES
('Napelempark állapotfelmérése', 'Fiktív Solarpark - A szektor', 'DemoQuad 01', DATE '2026-11-20', 18, 'planned', 'Kitalált oktatási feladat; nem valós repülési terv.'),
('Raktártető szemrevételezése', 'Fiktív Ipari Park - 2. csarnok', 'DemoQuad 02', DATE '2026-11-19', 12, 'active', 'Demóadat a státuszváltás bemutatásához.'),
('Gyakorlóterület térképezése', 'Fiktív Tesztmező', 'DemoQuad 01', DATE '2026-11-18', 24, 'completed', 'Lezárt mintafeladat; a 24 perc beleszámít az összesített repülési időbe.');

COMMIT;
