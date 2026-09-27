import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common import utcnow
from app.db import Base, UTCDateTime


class Decision(Base):
    """Append-only decision log; the latest row per target is the effective decision."""

    __tablename__ = "decisions"
    __table_args__ = (Index("ix_decisions_target", "target_type", "target_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(20))  # opportunity | action
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
