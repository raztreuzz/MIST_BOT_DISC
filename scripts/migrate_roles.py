#!/usr/bin/env python3
"""Script to migrate users.roles CSV -> JSON in SQLite DB used by MIST."""
from app.lists.storage import DB_PATH, migrate_roles_csv_to_json


def main():
    print("DB:", DB_PATH)
    updated = migrate_roles_csv_to_json()
    print(f"Migrated {updated} user role rows to JSON format.")


if __name__ == '__main__':
    main()
