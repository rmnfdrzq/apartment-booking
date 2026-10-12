"""Pydantic schemas for data validation and API serialization."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import BookingStatus

# Common email regex pattern to validate format without external dependencies
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# -----------------------------------------------------------------------------
# Apartment Schemas (Contract-First Definition)
# -----------------------------------------------------------------------------


class ApartmentBase(BaseModel):
    """Base fields for apartment listings."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255, description="Apartment listing title")
    description: Optional[str] = Field(None, description="Detailed description of the apartment")
    address: str = Field(..., min_length=1, max_length=255, description="Physical address")
    price_per_night: float = Field(..., gt=0, description="Price per night in euros")
    max_guests: int = Field(1, ge=1, description="Maximum number of guests allowed")


class ApartmentCreate(ApartmentBase):
    """Payload for creating a new apartment listing."""

    pass


class ApartmentUpdate(BaseModel):
    """Payload for updating an existing apartment listing."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    address: Optional[str] = Field(None, min_length=1, max_length=255)
    price_per_night: Optional[float] = Field(None, gt=0)
    max_guests: Optional[int] = Field(None, ge=1)


class ApartmentResponse(ApartmentBase):
    """Serialized apartment response."""

    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# -----------------------------------------------------------------------------
# Booking Schemas
# -----------------------------------------------------------------------------


class BookingBase(BaseModel):
    """Base fields for bookings."""

    model_config = ConfigDict(str_strip_whitespace=True)

    guest_name: str = Field(..., min_length=1, max_length=255, description="Full name of the guest")
    guest_email: str = Field(
        ...,
        pattern=EMAIL_REGEX,
        description="Valid contact email of the guest",
    )
    start_date: date = Field(..., description="Check-in date (inclusive)")
    end_date: date = Field(..., description="Check-out date (exclusive)")


class BookingCreate(BookingBase):
    """Payload for creating a new booking."""

    apartment_id: str = Field(..., min_length=1, description="ID of the apartment being booked")

    @model_validator(mode="after")
    def validate_date_order(self) -> "BookingCreate":
        """Ensure check-in date is strictly before check-out date."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date")
        return self


class BookingUpdate(BaseModel):
    """Payload for updating an existing booking."""

    model_config = ConfigDict(str_strip_whitespace=True)

    apartment_id: Optional[str] = Field(None, min_length=1, description="Move booking to a different apartment ID")
    guest_name: Optional[str] = Field(None, min_length=1, max_length=255)
    guest_email: Optional[str] = Field(None, pattern=EMAIL_REGEX)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_date_order(self) -> "BookingUpdate":
        """Ensure check-in is before check-out if both dates are provided."""
        if self.start_date is not None and self.end_date is not None:
            if self.start_date >= self.end_date:
                raise ValueError("start_date must be strictly before end_date")
        return self


class BookingResponse(BaseModel):
    """Serialized booking response."""

    id: str
    apartment_id: str
    guest_name: str
    guest_email: str
    start_date: date
    end_date: date
    total_price: float
    status: BookingStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
