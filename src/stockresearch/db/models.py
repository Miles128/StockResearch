"""SQLAlchemy database models."""

import decimal
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    holdings: Mapped[list["Holding"]] = relationship(back_populates="user", cascade="all, delete")
    watchlist: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    sector_preferences: Mapped[list["UserSectorPreference"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user", cascade="all, delete", uselist=False
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    mode_settings: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="preferences")


class UserSectorPreference(Base):
    __tablename__ = "user_sector_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sector: Mapped[str] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="sector_preferences")


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(6), index=True)
    name: Mapped[str] = mapped_column(String(50))
    cost_price: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 4))
    quantity: Mapped[int] = mapped_column(Integer)
    sector: Mapped[str] = mapped_column(String(50), default="未知")
    buy_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)

    user: Mapped["User"] = relationship(back_populates="holdings")

    @property
    def float_cost_price(self) -> float:
        """Convenience accessor that returns cost_price as float for arithmetic."""
        return float(self.cost_price)


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(6), index=True)
    name: Mapped[str] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="watchlist")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(100))
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    impact_level: Mapped[str] = mapped_column(String(20), default="normal")
    entities: Mapped[list[str]] = mapped_column(JSON, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(6), index=True)
    name: Mapped[str] = mapped_column(String(50))
    report_json: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RiskAlertRecord(Base):
    __tablename__ = "risk_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    symbol: Mapped[str | None] = mapped_column(String(6), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BriefingRecord(Base):
    """Auto-generated morning/closing briefing records."""

    __tablename__ = "briefing_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    user: Mapped["User"] = relationship(back_populates="briefings")


User.briefings = relationship("BriefingRecord", back_populates="user", cascade="all, delete")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    messages: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    checkpoint: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
