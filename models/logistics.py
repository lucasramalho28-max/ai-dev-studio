import os
from datetime import datetime, timezone

os.environ.setdefault('DISABLE_SQLALCHEMY_CEXT_RUNTIME', '1')

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class LogisticsUpload(Base):
    __tablename__ = 'logistics_uploads'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project: Mapped[str] = mapped_column(String(32), index=True)
    original_name: Mapped[str] = mapped_column(String(180))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    extension: Mapped[str] = mapped_column(String(10))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created: Mapped[str] = mapped_column(String(40), default=utc_now)


class LogisticsAnalysis(Base):
    __tablename__ = 'logistics_analyses'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project: Mapped[str] = mapped_column(String(32), index=True)
    upload_id: Mapped[str] = mapped_column(String(32), index=True)
    profile_json: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=utc_now)


class LogisticsIndicator(Base):
    __tablename__ = 'logistics_indicators'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    formula: Mapped[str] = mapped_column(Text)
    fields_json: Mapped[str] = mapped_column(Text)
    filters_json: Mapped[str] = mapped_column(Text, default='[]')
    unit: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80), default='')
    source: Mapped[str] = mapped_column(String(180), default='')
    updated: Mapped[str] = mapped_column(String(40), default=utc_now)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class LogisticsMemory(Base):
    __tablename__ = 'logistics_memory'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(100))
    value_json: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    updated: Mapped[str] = mapped_column(String(40), default=utc_now)


class LogisticsDashboard(Base):
    __tablename__ = 'logistics_dashboards'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project: Mapped[str] = mapped_column(String(32), index=True)
    upload_id: Mapped[str] = mapped_column(String(32), default='')
    title: Mapped[str] = mapped_column(String(180))
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='draft')
    result_json: Mapped[str] = mapped_column(Text, default='{}')
    created: Mapped[str] = mapped_column(String(40), default=utc_now)


class LogisticsActivity(Base):
    __tablename__ = 'logistics_activities'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=utc_now)
