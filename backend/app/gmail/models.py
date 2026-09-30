from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime


class GmailConnection(Base):
    """Single row: the read-only Gmail grant, separate from the calendar grant (ADR 0009)."""

    __tablename__ = "gmail_connection"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    protected_tokens: Mapped[str | None] = mapped_column(Text)
    protected_oauth: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(40), default="disconnected")
    detail: Mapped[str | None] = mapped_column(Text)


class GmailMessage(Base):
    """A labelled message that was already sent to the LLM; never sent twice. No body stored."""

    __tablename__ = "gmail_messages"
    message_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20))  # ok | empty | skipped
    found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
