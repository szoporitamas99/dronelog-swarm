"""PostgreSQL hozzáférés. Minden kérés saját, automatikusan lezárt kapcsolatot kap.

A stateless API-példányok között csak az adatbázisban van megosztott állapot.
Az SQL paraméterezett; a PATCH oszlopnevei egy rögzített engedélylistából jönnek.
"""

import logging
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

LOGGER = logging.getLogger("dronelog.database")
COLUMNS = "id, title, location, aircraft, mission_date, flight_minutes, status, notes, created_at"
PATCH_FIELDS = frozenset({"title", "location", "aircraft", "mission_date", "flight_minutes", "status", "notes"})


class DatabaseUnavailable(Exception):
    """A kliensnek részletek és titkok nélkül jelezhető adatbázishiba."""


def read_required_secret(path: str, *, minimum_length: int = 1) -> str:
    """Nincs beégetett jelszó vagy környezeti változóból vett titok-tartalék."""
    value = Path(path).read_text(encoding="utf-8").strip()
    if len(value) < minimum_length:
        raise ValueError("A szükséges titok hiányzik vagy túl rövid.")
    return value


@contextmanager
def database_cursor():
    try:
        password = read_required_secret(os.getenv("DB_PASSWORD_FILE", "/run/secrets/db_password"))
        with psycopg.connect(
            host=os.getenv("DB_HOST", "db"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "dronelog"),
            user=os.getenv("DB_USER", "dronelog"),
            password=password,
            connect_timeout=3,
            options="-c statement_timeout=5000 -c lock_timeout=3000",
            row_factory=dict_row,
            application_name="dronelog-api",
        ) as connection:
            with connection.cursor() as cursor:
                yield cursor
        # A psycopg kapcsolat context managere siker esetén commitol, hibánál rollbackel.
    except (psycopg.Error, OSError, ValueError) as error:
        # A teljes kivételszöveg kapcsolati adatokat tartalmazhat; azt nem naplózzuk.
        LOGGER.warning("Adatbáziskérés sikertelen: %s", type(error).__name__)
        raise DatabaseUnavailable() from error


class MissionRepository:
    def health(self) -> None:
        with database_cursor() as cursor:
            # Nemcsak a szerver, hanem az alkalmazás táblája is legyen használható.
            cursor.execute("SELECT id FROM missions LIMIT 1")
            cursor.fetchone()

    def list(self, limit: int, offset: int) -> dict:
        with database_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM missions")
            count = cursor.fetchone()["count"]
            cursor.execute(
                f"SELECT {COLUMNS} FROM missions ORDER BY mission_date DESC, id DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            return {"items": cursor.fetchall(), "count": count}

    def create(self, fields: dict) -> dict:
        with database_cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO missions (title, location, aircraft, mission_date, flight_minutes, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {COLUMNS}""",
                tuple(fields[name] for name in ("title", "location", "aircraft", "mission_date", "flight_minutes", "status", "notes")),
            )
            return cursor.fetchone()

    def update(self, mission_id: int, fields: dict) -> dict | None:
        if not fields or not fields.keys() <= PATCH_FIELDS:
            raise ValueError("Érvénytelen módosítandó mezők.")
        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(name)) for name in fields
        )
        query = sql.SQL("UPDATE missions SET {} WHERE id = %s RETURNING " + COLUMNS).format(assignments)
        with database_cursor() as cursor:
            cursor.execute(query, (*fields.values(), mission_id))
            return cursor.fetchone()

    def delete(self, mission_id: int) -> bool:
        with database_cursor() as cursor:
            cursor.execute("DELETE FROM missions WHERE id = %s RETURNING id", (mission_id,))
            return cursor.fetchone() is not None

    def stats(self) -> dict:
        with database_cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'planned') AS planned,
                   COUNT(*) FILTER (WHERE status = 'active') AS active,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                   COALESCE(SUM(flight_minutes) FILTER (WHERE status = 'completed'), 0) AS flight_minutes
                   FROM missions"""
            )
            return cursor.fetchone()
