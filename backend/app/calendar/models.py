from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CalendarConnection(Base):
    __tablename__ = "calendar_connection"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    calendar_id: Mapped[str | None] = mapped_column(String(500))
    protected_tokens: Mapped[str | None] = mapped_column(Text)
    protected_oauth: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(40), default="disconnected")
    detail: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
