import json
from pathlib import Path
from typing import Any

from app.lists.models import SavedList


DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "lists.json"


def _read_data() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {}
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_data(data: dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_list(guild_id: int, name: str, kind: str) -> bool:
    data = _read_data()
    guild_key = str(guild_id)
    data.setdefault(guild_key, {"lists": {}})
    
    if name in data[guild_key]["lists"]:
        return False
    
    data[guild_key]["lists"][name] = {"name": name, "kind": kind, "items": []}
    _write_data(data)
    return True


def add_to_list(guild_id: int, name: str, url: str) -> bool:
    data = _read_data()
    guild_key = str(guild_id)
    
    if guild_key not in data or name not in data[guild_key]["lists"]:
        return False
    
    data[guild_key]["lists"][name]["items"].append(url)
    _write_data(data)
    return True


def get_list(guild_id: int, name: str) -> SavedList | None:
    data = _read_data()
    guild = data.get(str(guild_id), {})
    raw_list = guild.get("lists", {}).get(name)
    
    if raw_list is None:
        return None
    
    return SavedList(
        name=raw_list["name"],
        kind=raw_list["kind"],
        items=list(raw_list.get("items", []))
    )


def list_lists(guild_id: int) -> list[SavedList]:
    data = _read_data()
    guild = data.get(str(guild_id), {})
    return [
        SavedList(
            name=item["name"],
            kind=item["kind"],
            items=list(item.get("items", []))
        )
        for item in guild.get("lists", {}).values()
    ]
