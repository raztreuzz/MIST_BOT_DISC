from pathlib import Path
from typing import Optional
from types import SimpleNamespace

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from app.config import DATABASE_URL

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True, nullable=False)
    discord_id = Column(Integer, nullable=False)
    display_name = Column(String(200))
    roles = Column(Text)


class SavedList(Base):
    __tablename__ = "saved_lists"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    kind = Column(String(50), nullable=False)
    creator_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    items = relationship("ListItem", back_populates="saved_list", cascade="all, delete-orphan")


class ListItem(Base):
    __tablename__ = "list_items"
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey("saved_lists.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    saved_list = relationship("SavedList", back_populates="items")


class AiInteraction(Base):
    __tablename__ = "ai_interactions"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, index=True, nullable=False)
    channel_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=False)
    display_name = Column(String(200), nullable=True)
    model = Column(String(200), nullable=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# create engine and session
_engine = create_engine(DATABASE_URL, future=True)
_Session = sessionmaker(bind=_engine, expire_on_commit=False)

# ensure tables exist
Base.metadata.create_all(_engine)


# Storage API

def create_list(guild_id: int, name: str, kind: str, creator_id: Optional[int] = None) -> bool:
    with _Session() as s:
        existing = s.query(SavedList).filter_by(guild_id=guild_id, name=name).first()
        if existing:
            return False
        lst = SavedList(guild_id=guild_id, name=name, kind=kind, creator_id=creator_id)
        s.add(lst)
        s.commit()
        return True


def add_to_list(guild_id: int, name: str, url: str) -> bool:
    with _Session() as s:
        lst = s.query(SavedList).filter_by(guild_id=guild_id, name=name).first()
        if lst is None:
            return False
        max_pos = s.query(func.coalesce(func.max(ListItem.position), 0)).filter(ListItem.list_id == lst.id).scalar()
        item = ListItem(list_id=lst.id, url=url, position=(max_pos or 0) + 1)
        s.add(item)
        s.commit()
        return True


def delete_list(guild_id: int, name: str) -> Optional[int]:
    with _Session() as s:
        lst = s.query(SavedList).filter_by(guild_id=guild_id, name=name).first()
        if lst is None:
            return None
        item_count = len(lst.items)
        s.delete(lst)
        s.commit()
        return item_count


def ensure_user(guild_id: int, discord_id: int, display_name: Optional[str] = None, roles: Optional[str] = None) -> None:
    with _Session() as s:
        user = s.query(User).filter_by(guild_id=guild_id, discord_id=discord_id).first()
        if user:
            user.display_name = display_name
            user.roles = roles
        else:
            user = User(guild_id=guild_id, discord_id=discord_id, display_name=display_name, roles=roles)
            s.add(user)
        s.commit()


def get_user(guild_id: int, discord_id: int) -> Optional[dict]:
    with _Session() as s:
        user = s.query(User).filter_by(guild_id=guild_id, discord_id=discord_id).first()
        if not user:
            return None
        return {"discord_id": user.discord_id, "display_name": user.display_name, "roles": user.roles}


def migrate_roles_csv_to_json() -> int:
    updated = 0
    with _Session() as s:
        users = s.query(User).filter(User.roles != None).all()
        for user in users:
            raw = (user.roles or "").strip()
            if not raw:
                continue
            if raw.startswith("{") or raw.startswith("["):
                continue
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            import json

            user.roles = json.dumps({"ids": [], "names": parts}, ensure_ascii=False)
            updated += 1
        s.commit()
    return updated


def get_list(guild_id: int, name: str) -> Optional[SimpleNamespace]:
    with _Session() as s:
        lst = s.query(SavedList).filter_by(guild_id=guild_id, name=name).first()
        if not lst:
            return None
        # load items
        items = [item.url for item in sorted(lst.items, key=lambda i: i.position)]
        return SimpleNamespace(name=lst.name, kind=lst.kind, items=items)


def list_lists(guild_id: int) -> list:
    with _Session() as s:
        rows = s.query(SavedList).filter_by(guild_id=guild_id).order_by(SavedList.name.asc()).all()
        result = []
        for r in rows:
            items = [item.url for item in sorted(r.items, key=lambda i: i.position)]
            result.append(SimpleNamespace(name=r.name, kind=r.kind, items=items))
        return result


def record_ai_interaction(
    guild_id: int,
    channel_id: Optional[int],
    user_id: int,
    display_name: Optional[str],
    model: Optional[str],
    prompt: str,
    response: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    with _Session() as s:
        row = AiInteraction(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            display_name=display_name,
            model=model,
            prompt=prompt[:2000],
            response=response[:4000] if response else None,
            error=error[:1000] if error else None,
        )
        s.add(row)
        s.commit()


def recent_ai_interactions(guild_id: int, limit: int = 10) -> list:
    limit = max(1, min(limit, 25))
    with _Session() as s:
        rows = (
            s.query(AiInteraction)
            .filter_by(guild_id=guild_id)
            .order_by(AiInteraction.id.desc())
            .limit(limit)
            .all()
        )
        return [
            SimpleNamespace(
                id=row.id,
                channel_id=row.channel_id,
                user_id=row.user_id,
                display_name=row.display_name,
                model=row.model,
                prompt=row.prompt,
                response=row.response,
                error=row.error,
                created_at=row.created_at,
            )
            for row in rows
        ]


def storage_stats(guild_id: int) -> SimpleNamespace:
    with _Session() as s:
        lists_count = s.query(SavedList).filter_by(guild_id=guild_id).count()
        list_ids = [row.id for row in s.query(SavedList.id).filter_by(guild_id=guild_id).all()]
        items_count = s.query(ListItem).filter(ListItem.list_id.in_(list_ids)).count() if list_ids else 0
        users_count = s.query(User).filter_by(guild_id=guild_id).count()
        ai_logs_count = s.query(AiInteraction).filter_by(guild_id=guild_id).count()
        return SimpleNamespace(
            lists=lists_count,
            items=items_count,
            users=users_count,
            ai_logs=ai_logs_count,
            database_url=DATABASE_URL,
        )
