from datetime import date, time, datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class RegisterPatient(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    password: str = Field(min_length=8)
    address: str = Field(min_length=5, max_length=500)
    locality: str | None = None
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    pin_code: str = Field(min_length=4, max_length=20)

class RegisterDoctor(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    password: str = Field(min_length=8)
    registration_number: str
    qualifications: str
    specialisations: str
    experience_years: int = Field(ge=0, le=80)
    bio: str | None = None
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    medical_college: str = Field(min_length=2, max_length=200)
    previous_workplaces: list[str] = Field(default_factory=list, max_length=20)

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class ProfileOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    model_config = ConfigDict(from_attributes=True)

class ChamberCreate(BaseModel):
    name: str
    address: str
    locality: str | None = None
    city: str
    state: str
    pin_code: str | None = None

class ServiceCreate(BaseModel):
    chamber_id: int
    name: str
    description: str | None = None
    fee: float = Field(ge=0)
    duration_minutes: int = Field(ge=5, le=240)

class AvailabilityCreate(BaseModel):
    chamber_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None

class AppointmentCreate(BaseModel):
    doctor_id: int
    chamber_id: int
    service_id: int
    starts_at: datetime

class CancelInput(BaseModel):
    reason: str | None = None

class SymptomSearch(BaseModel):
    symptoms: str = Field(min_length=2, max_length=2000)

class GeocodeInput(BaseModel):
    address: str = Field(min_length=5, max_length=500)


class ForgotPasswordInput(BaseModel):
    email: EmailStr

class ResetPasswordInput(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=10)

class GoogleAuthInput(BaseModel):
    credential: str = Field(min_length=20)

class PatientProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, min_length=7, max_length=40)
    address: str | None = Field(default=None, min_length=5, max_length=500)
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    pin_code: str | None = None

class DoctorProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, min_length=7, max_length=40)
    qualifications: str | None = None
    specialisations: str | None = None
    experience_years: int | None = Field(default=None, ge=0, le=80)
    bio: str | None = None
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    medical_college: str | None = None
    previous_workplaces: list[str] | None = None
