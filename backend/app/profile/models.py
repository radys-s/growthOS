import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common import EducationLevel, utcnow
from app.db import Base, UTCDateTime


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[date | None] = mapped_column(Date)
    country: Mapped[str] = mapped_column(String(2), default="CZ")
    education_level: Mapped[str] = mapped_column(String(20), default=EducationLevel.HIGH_SCHOOL)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    max_cost_eur: Mapped[int | None] = mapped_column(Integer)
    weekly_hours_budget: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    skills: Mapped[list["ProfileSkill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileSkill.signal"
    )
    items: Mapped[list["ProfileItem"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileItem.created_at"
    )


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    __table_args__ = (UniqueConstraint("profile_id", "signal"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    signal: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(Integer)

    profile: Mapped[Profile] = relationship(back_populates="skills")


class ProfileItem(Base):
    __tablename__ = "profile_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(500))
    signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    strength: Mapped[int] = mapped_column(Integer)
    achieved_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    profile: Mapped[Profile] = relationship(back_populates="items")
