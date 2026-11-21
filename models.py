import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlalchemy.orm import DeclarativeBase

from database import engine


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Text, primary_key=True, default=_uuid)
    status = Column(Text, nullable=False, default="pending")
    workflow_type = Column(Text, nullable=False, default="video")
    image_paths = Column(Text, nullable=False, default="[]")
    specs = Column(Text, nullable=False, default="{}")
    params = Column(Text, nullable=False, default="{}")
    llm_model = Column(Text, nullable=False, default="")
    video_model = Column(Text, nullable=False, default="")
    image_model = Column(Text, nullable=False, default="")
    result = Column(Text, nullable=False, default="{}")
    user_requirements = Column(Text, nullable=False, default="")
    error_message = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, default=_now)
    updated_at = Column(Text, nullable=False, default=_now)


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id = Column(Text, primary_key=True, default=_uuid)
    task_id = Column(Text, nullable=False, index=True)
    shot_index = Column(Text, nullable=False)
    prompt = Column(Text, nullable=False, default="")
    input_image = Column(Text, nullable=False, default="")
    video_path = Column(Text, nullable=False, default="")
    status = Column(Text, nullable=False, default="pending")
    sophnet_task_id = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, default=_now)
    updated_at = Column(Text, nullable=False, default=_now)


class Config(Base):
    __tablename__ = "config"

    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(Text, nullable=False, default=_now)