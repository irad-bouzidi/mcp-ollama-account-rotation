from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class UsageLog(Base, TimestampMixin):
    __tablename__ = "usage_logs"

    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[object] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[object] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    request_type: Mapped[str] = mapped_column(String(50), default="chat")
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="usage_logs")
    provider: Mapped["Provider"] = relationship()
