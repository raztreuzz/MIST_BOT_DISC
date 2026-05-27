#!/usr/bin/env python3
"""Script to migrate users.roles CSV -> JSON in the configured MIST DB."""

from app.config import DATABASE_URL
from app.lists.storage import migrate_roles_csv_to_json


def main():
    print("DB:", DATABASE_URL)
    updated = migrate_roles_csv_to_json()
    print(f"Migrated {updated} user role rows to JSON format.")


if __name__ == "__main__":
    main()
