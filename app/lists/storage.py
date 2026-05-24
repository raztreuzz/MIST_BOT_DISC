import sqlite3
from pathlib import Path

from app.lists.models import SavedList


DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mist.sqlite3"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _init_db(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            creator_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, name)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY(list_id) REFERENCES saved_lists(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            discord_id INTEGER NOT NULL,
            display_name TEXT,
            roles TEXT,
            UNIQUE(guild_id, discord_id)
        )
        """
    )
    connection.commit()


def create_list(guild_id: int, name: str, kind: str, creator_id: int | None = None) -> bool:
    """Create a named list for a guild. Optionally record the creator's discord id."""
    with _connect() as connection:
        _init_db(connection)
        try:
            connection.execute(
                "INSERT INTO saved_lists (guild_id, name, kind, creator_id) VALUES (?, ?, ?, ?)",
                (guild_id, name, kind, creator_id),
            )
            connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def add_to_list(guild_id: int, name: str, url: str) -> bool:
    with _connect() as connection:
        _init_db(connection)
        list_row = connection.execute(
            "SELECT id FROM saved_lists WHERE guild_id = ? AND name = ?",
            (guild_id, name),
        ).fetchone()

        if list_row is None:
            return False

        next_position_row = connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM list_items WHERE list_id = ?",
            (list_row["id"],),
        ).fetchone()

        connection.execute(
            "INSERT INTO list_items (list_id, url, position) VALUES (?, ?, ?)",
            (list_row["id"], url, next_position_row["next_position"]),
        )
        connection.commit()
        return True


def ensure_user(guild_id: int, discord_id: int, display_name: str | None = None, roles: str | None = None) -> None:
    """Insert or update a user profile for quick lookups."""
    with _connect() as connection:
        _init_db(connection)
        connection.execute(
            "INSERT INTO users (guild_id, discord_id, display_name, roles) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(guild_id, discord_id) DO UPDATE SET display_name=excluded.display_name, roles=excluded.roles",
            (guild_id, discord_id, display_name, roles),
        )
        connection.commit()


def get_user(guild_id: int, discord_id: int) -> dict | None:
    with _connect() as connection:
        _init_db(connection)
        row = connection.execute(
            "SELECT discord_id, display_name, roles FROM users WHERE guild_id = ? AND discord_id = ?",
            (guild_id, discord_id),
        ).fetchone()
        if row is None:
            return None
        return {"discord_id": row["discord_id"], "display_name": row["display_name"], "roles": row["roles"]}


def migrate_roles_csv_to_json() -> int:
    """Migrate users.roles stored as CSV of names to JSON {ids:[], names:[]}.

    Returns the number of rows updated.
    """
    import json

    updated = 0
    with _connect() as connection:
        _init_db(connection)
        rows = connection.execute("SELECT guild_id, discord_id, roles FROM users WHERE roles IS NOT NULL AND roles != ''").fetchall()
        for row in rows:
            raw = row["roles"]
            # Skip if already JSON (starts with [ or {)
            if raw.strip().startswith(('{', '[')):
                continue
            # assume CSV of role names
            parts = [p.strip() for p in raw.split(',') if p.strip()]
            roles_json = json.dumps({"ids": [], "names": parts}, ensure_ascii=False)
            connection.execute(
                "UPDATE users SET roles = ? WHERE guild_id = ? AND discord_id = ?",
                (roles_json, row["guild_id"], row["discord_id"]),
            )
            updated += 1
        connection.commit()
    return updated


def get_list(guild_id: int, name: str) -> SavedList | None:
    with _connect() as connection:
        _init_db(connection)
        list_row = connection.execute(
            "SELECT id, name, kind FROM saved_lists WHERE guild_id = ? AND name = ?",
            (guild_id, name),
        ).fetchone()

        if list_row is None:
            return None

        items = connection.execute(
            "SELECT url FROM list_items WHERE list_id = ? ORDER BY position ASC",
            (list_row["id"],),
        ).fetchall()

        return SavedList(
            name=list_row["name"],
            kind=list_row["kind"],
            items=[item["url"] for item in items],
        )


def list_lists(guild_id: int) -> list[SavedList]:
    with _connect() as connection:
        _init_db(connection)
        rows = connection.execute(
            "SELECT id, name, kind FROM saved_lists WHERE guild_id = ? ORDER BY name ASC",
            (guild_id,),
        ).fetchall()

        result: list[SavedList] = []
        for list_row in rows:
            items = connection.execute(
                "SELECT url FROM list_items WHERE list_id = ? ORDER BY position ASC",
                (list_row["id"],),
            ).fetchall()
            result.append(
                SavedList(
                    name=list_row["name"],
                    kind=list_row["kind"],
                    items=[item["url"] for item in items],
                )
            )

        return result
