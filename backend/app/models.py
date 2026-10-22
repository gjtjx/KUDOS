from datetime import date, time
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ChatInput(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    patient_id: Literal["P001"] = "P001"
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")

    @field_validator("message")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Message must not be blank")
        return v.strip()

class BookingInput(StrictModel):
    patient_id: Literal["P001"] = "P001"
    doctor_id: str = Field(pattern=r"^D[0-9]{3}$")
    treatment_id: str = Field(pattern=r"^T[0-9]{3}$")
    booking_date: date
    booking_time: time
    notes: str = Field(default="", max_length=1000)
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")

    @field_validator("booking_time")
    @classmethod
    def local_time(cls, value):
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Use clinic-local HH:MM without seconds or timezone")
        return value

