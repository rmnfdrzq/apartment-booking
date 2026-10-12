"""SQLAlchemy ORM models for Apartments and Bookings."""

import enum
import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BookingStatus(str, enum.Enum):
    """Lifecycle status of a booking."""

    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class Apartment(Base):
    """Apartment property listing available for rental."""

    __tablename__ = "apartments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    price_per_night: Mapped[float] = mapped_column(Float, nullable=False)
    max_guests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships: Deletion of apartments with active bookings is RESTRICTED
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="apartment",
        passive_deletes="all",
    )


class Booking(Base):
    """Guest stay reservation for an apartment."""

    __tablename__ = "bookings"
    __table_args__ = (
        # High-performance composite index for date overlap queries
        Index(
            "ix_bookings_apartment_status_dates",
            "apartment_id",
            "status",
            "start_date",
            "end_date",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    apartment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("apartments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        default=BookingStatus.CONFIRMED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    apartment: Mapped["Apartment"] = relationship(
        "Apartment",
        back_populates="bookings",
    )
