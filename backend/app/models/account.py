from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_id: Mapped[object] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_token: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_depleted: Mapped[bool] = mapped_column(Boolean, default=False)
    credits_remaining: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requests_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_reset: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    provider: Mapped["Provider"] = relationship(back_populates="accounts")
    usage_logs: Mapped[list["UsageLog"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
