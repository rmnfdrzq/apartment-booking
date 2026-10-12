"""Pydantic schemas for data validation and API serialization."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import BookingStatus

# Common email regex pattern to validate format without external dependencies
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# -----------------------------------------------------------------------------
# Apartment Schemas (Contract-First Definition)
# -----------------------------------------------------------------------------


APARTMENT_TEXT_MAX_LENGTH = 255
APARTMENT_DESCRIPTION_MAX_LENGTH = 5000
APARTMENT_MAX_PRICE_PER_NIGHT = 1_000_000.0
APARTMENT_MAX_GUESTS_LIMIT = 100

# Fields backed by NOT NULL columns: they may be omitted in an update, but never set to null.
APARTMENT_REQUIRED_FIELDS = ("title", "address", "price_per_night", "max_guests")


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    """Store empty/whitespace-only descriptions as NULL instead of an empty string."""
    if value is not None and not value.strip():
        return None
    return value


class ApartmentBase(BaseModel):
    """Base fields for apartment listings."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=APARTMENT_TEXT_MAX_LENGTH,
        description="Apartment listing title",
    )
    description: Optional[str] = Field(
        None,
        max_length=APARTMENT_DESCRIPTION_MAX_LENGTH,
        description="Detailed description of the apartment",
    )
    address: str = Field(
        ...,
        min_length=1,
        max_length=APARTMENT_TEXT_MAX_LENGTH,
        description="Physical address",
    )
    price_per_night: float = Field(
        ...,
        gt=0,
        le=APARTMENT_MAX_PRICE_PER_NIGHT,
        allow_inf_nan=False,
        description="Price per night in euros",
    )
    max_guests: int = Field(
        1,
        ge=1,
        le=APARTMENT_MAX_GUESTS_LIMIT,
        description="Maximum number of guests allowed",
    )

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        """Convert blank descriptions to null."""
        return _blank_to_none(value)


class ApartmentCreate(ApartmentBase):
    """Payload for creating a new apartment listing."""

    pass


class ApartmentUpdate(BaseModel):
    """Partial update payload: only the fields sent in the request body are changed."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(None, min_length=1, max_length=APARTMENT_TEXT_MAX_LENGTH)
    description: Optional[str] = Field(
        None,
        max_length=APARTMENT_DESCRIPTION_MAX_LENGTH,
        description="Send null or an empty string to clear the description",
    )
    address: Optional[str] = Field(None, min_length=1, max_length=APARTMENT_TEXT_MAX_LENGTH)
    price_per_night: Optional[float] = Field(
        None,
        gt=0,
        le=APARTMENT_MAX_PRICE_PER_NIGHT,
        allow_inf_nan=False,
    )
    max_guests: Optional[int] = Field(None, ge=1, le=APARTMENT_MAX_GUESTS_LIMIT)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        """Convert blank descriptions to null."""
        return _blank_to_none(value)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "ApartmentUpdate":
        """Required fields may be omitted, but an explicit null would violate NOT NULL columns."""
        nulled = [
            name for name in APARTMENT_REQUIRED_FIELDS if name in self.model_fields_set and getattr(self, name) is None
        ]
        if nulled:
            raise ValueError(f"Fields cannot be null: {', '.join(nulled)}")
        return self


class ApartmentResponse(BaseModel):
    """Serialized apartment response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: Optional[str]
    address: str
    price_per_night: float
    max_guests: int
    created_at: datetime


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
