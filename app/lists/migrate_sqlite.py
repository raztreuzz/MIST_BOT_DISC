import argparse
import sqlite3
from pathlib import Path

from app.config import DATABASE_URL
from app.lists.storage import (
    add_to_list,
    create_list,
    ensure_user,
    get_list,
    record_ai_interaction,
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _migrate_users(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "users"):
        return 0

    count = 0
    rows = conn.execute("SELECT guild_id, discord_id, display_name, roles FROM users")
    for row in rows:
        ensure_user(
            int(row["guild_id"]),
            int(row["discord_id"]),
            row["display_name"],
            row["roles"],
        )
        count += 1
    return count


def _migrate_lists(conn: sqlite3.Connection, append_existing: bool) -> tuple[int, int, int]:
    if not _table_exists(conn, "saved_lists") or not _table_exists(conn, "list_items"):
        return 0, 0, 0

    lists_created = 0
    lists_skipped = 0
    items_added = 0
    rows = conn.execute(
        "SELECT id, guild_id, name, kind, creator_id FROM saved_lists ORDER BY id"
    )
    for row in rows:
        guild_id = int(row["guild_id"])
        name = row["name"]
        current = get_list(guild_id, name)
        if current is None:
            create_list(guild_id, name, row["kind"], row["creator_id"])
            lists_created += 1
        elif current.items and not append_existing:
            lists_skipped += 1
            continue

        item_rows = conn.execute(
            "SELECT url FROM list_items WHERE list_id = ? ORDER BY position, id",
            (row["id"],),
        )
        for item in item_rows:
            if add_to_list(guild_id, name, item["url"]):
                items_added += 1

    return lists_created, lists_skipped, items_added


def _migrate_ai_logs(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "ai_interactions"):
        return 0

    count = 0
    rows = conn.execute(
        """
        SELECT guild_id, channel_id, user_id, display_name, model, prompt, response, error
        FROM ai_interactions
        ORDER BY id
        """
    )
    for row in rows:
        record_ai_interaction(
            int(row["guild_id"]),
            int(row["channel_id"]) if row["channel_id"] is not None else None,
            int(row["user_id"]),
            row["display_name"],
            row["model"],
            row["prompt"],
            row["response"],
            row["error"],
        )
        count += 1
    return count


def migrate(sqlite_path: Path, include_ai_logs: bool, append_existing: bool) -> dict:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"No existe la base SQLite: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        users = _migrate_users(conn)
        lists_created, lists_skipped, items_added = _migrate_lists(conn, append_existing)
        ai_logs = _migrate_ai_logs(conn) if include_ai_logs else 0
    finally:
        conn.close()

    return {
        "users": users,
        "lists_created": lists_created,
        "lists_skipped": lists_skipped,
        "items_added": items_added,
        "ai_logs": ai_logs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra datos de SQLite hacia la BD configurada de MIST.")
    parser.add_argument("sqlite_path", help="Ruta al archivo SQLite viejo, por ejemplo /app/data/mist.sqlite3")
    parser.add_argument("--include-ai-logs", action="store_true", help="También migra logs de preguntas a MIST.")
    parser.add_argument(
        "--append-existing",
        action="store_true",
        help="Agrega canciones aunque la lista ya exista y tenga items.",
    )
    args = parser.parse_args()

    result = migrate(Path(args.sqlite_path), args.include_ai_logs, args.append_existing)
    print(f"Destino: {DATABASE_URL}")
    print(f"Usuarios migrados/actualizados: {result['users']}")
    print(f"Listas creadas: {result['lists_created']}")
    print(f"Listas existentes omitidas: {result['lists_skipped']}")
    print(f"Canciones agregadas: {result['items_added']}")
    print(f"Logs IA migrados: {result['ai_logs']}")


if __name__ == "__main__":
    main()
