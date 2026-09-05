from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountDatabaseProfile(Base):
    __tablename__ = "account_database_profiles"
    __table_args__ = (
        UniqueConstraint("member_id", "connection_id", name="uq_account_database_profiles_member_connection"),
    )

    account_database_profiles_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("agentstudio_members.id"), index=True)
    connection_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(300), default="")
    db_type: Mapped[str] = mapped_column(String(50), default="postgresql", index=True)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    credential_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_storage: Mapped[str] = mapped_column(String(80), default="WINDOWS_DPAPI")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AccountSettingProfile(Base):
    __tablename__ = "account_setting_profiles"
    __table_args__ = (
        UniqueConstraint("member_id", "setting_group", "profile_name", name="uq_account_setting_profiles_member_group_name"),
    )

    account_setting_profiles_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("agentstudio_members.id"), index=True)
    setting_group: Mapped[str] = mapped_column(String(100), index=True)
    profile_name: Mapped[str] = mapped_column(String(300), default="")
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AccountProjectSetting(Base):
    __tablename__ = "account_project_settings"
    __table_args__ = (
        UniqueConstraint("member_id", "project_key", "setting_group", "setting_key", name="uq_account_project_settings_member_project_group_key"),
    )

    account_project_settings_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("agentstudio_members.id"), index=True)
    project_root: Mapped[str] = mapped_column(String(1400), default="")
    project_key: Mapped[str] = mapped_column(String(1400), default="", index=True)
    setting_group: Mapped[str] = mapped_column(String(100), index=True)
    setting_key: Mapped[str] = mapped_column(String(150), default="default", index=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectSettingHistory(Base):
    __tablename__ = "project_setting_histories"

    project_setting_histories_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("agentstudio_members.id"), index=True)
    project_root: Mapped[str] = mapped_column(String(1400), default="")
    project_key: Mapped[str] = mapped_column(String(1400), default="", index=True)
    category: Mapped[str] = mapped_column(String(100), default="GENERAL", index=True)
    action: Mapped[str] = mapped_column(String(80), default="UPDATE", index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    before_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
