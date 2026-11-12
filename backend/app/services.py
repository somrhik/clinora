
import math
import asyncio
import time
import httpx

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.models import (
    User,
    PatientProfile,
    DoctorProfile,
    Chamber,
    DoctorService,
    Availability,
    Appointment,
    QueueCounter,
    Notification,
    SymptomMapping,
)

from app.schemas import AppointmentCreate


# ---------------------------------------------------------
# OPENSTREETMAP NOMINATIM GEOCODING
# ---------------------------------------------------------

# Nominatim public API usage:
# - Maximum 1 request per second.
# - Custom User-Agent required.
# - Cache successful results.
# - Geocode only when an address is saved or updated.

_NOMINATIM_LOCK = asyncio.Lock()
_NOMINATIM_LAST_REQUEST = 0.0
_NOMINATIM_CACHE: dict[str, dict] = {}


async def geocode_address(address: str):
    """Convert an address into latitude and longitude using Nominatim."""

    global _NOMINATIM_LAST_REQUEST

    cleaned_address = ", ".join(
        part.strip() for part in address.split(",") if part.strip()
    )

    if not cleaned_address:
        return None

    cache_key = cleaned_address.casefold()

    if cache_key in _NOMINATIM_CACHE:
        return _NOMINATIM_CACHE[cache_key]

    async with _NOMINATIM_LOCK:

        if cache_key in _NOMINATIM_CACHE:
            return _NOMINATIM_CACHE[cache_key]

        wait_seconds = 1.05 - (
            time.monotonic() - _NOMINATIM_LAST_REQUEST
        )

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        try:
            async with httpx.AsyncClient(
                timeout=15,
                headers={
                    "User-Agent": (
                        "Clinora/1.0 "
                        "(doctor discovery and appointment platform)"
                    )
                },
            ) as client:

                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": cleaned_address,
                        "format": "jsonv2",
                        "limit": 1,
                        "countrycodes": "in",
                    },
                )

            _NOMINATIM_LAST_REQUEST = time.monotonic()

            response.raise_for_status()
            results = response.json()

        except (httpx.HTTPError, ValueError):
            return None

        if not results:
            return None

        result = results[0]

        try:
            location = {
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"]),
                "formatted_address": result.get(
                    "display_name",
                    cleaned_address,
                ),
            }

        except (KeyError, TypeError, ValueError):
            return None

        _NOMINATIM_CACHE[cache_key] = location

        return location


def patient_address(profile: PatientProfile) -> str:
    """Build a locality-level address for patient geocoding."""

    return ", ".join(
        part
        for part in [
            profile.locality,
            profile.city,
            profile.state,
            profile.pin_code,
            "India",
        ]
        if part
    )


# ---------------------------------------------------------
# SYMPTOM MATCHING AND EMERGENCY WARNINGS
# ---------------------------------------------------------

EMERGENCY_TERMS = [
    "severe chest pain",
    "crushing chest pain",
    "difficulty breathing",
    "cannot breathe",
    "severe shortness of breath",
    "face drooping",
    "arm weakness",
    "speech difficulty",
    "sudden loss of consciousness",
    "uncontrolled bleeding",
    "stroke symptoms",
]


DEFAULT_MAPPINGS = {
    "rash": ["Dermatology"],
    "itch": ["Dermatology"],
    "skin": ["Dermatology"],

    "palpitation": ["Cardiology"],
    "heart": ["Cardiology"],

    "blurred vision": ["Ophthalmology"],
    "eye": ["Ophthalmology"],

    "tooth": ["Dentistry"],
    "gum": ["Dentistry"],

    "joint": ["Orthopaedics"],
    "bone": ["Orthopaedics"],

    "headache": ["Neurology"],
    "migraine": ["Neurology"],

    "cough": ["Pulmonology"],
    "breathlessness": ["Pulmonology"],

    "stomach": ["Gastroenterology"],
    "digestive": ["Gastroenterology"],

    "diabetes": ["Endocrinology", "Diabetology"],

    "ear": ["ENT"],
    "throat": ["ENT"],
    "nose": ["ENT"],
}


def emergency_matches(text: str):
    value = text.lower()

    return [
        term
        for term in EMERGENCY_TERMS
        if term in value
    ]


def match_specialisations(db: Session, text: str):
    value = text.lower()
    found = set()

    mappings = db.scalars(
        select(SymptomMapping)
    ).all()

    for item in mappings:
        if item.keyword.lower() in value:
            found.add(item.specialisation)

    for keyword, specialisations in DEFAULT_MAPPINGS.items():
        if keyword in value:
            found.update(specialisations)

    return sorted(found)


# ---------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------

def notify(
    db: Session,
    user_id: int,
    title: str,
    message: str,
):
    db.add(
        Notification(
            user_id=user_id,
            title=title,
            message=message,
        )
    )


# ---------------------------------------------------------
# DISTANCE CALCULATION
# ---------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return radius * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )


# ---------------------------------------------------------
# DOCTOR DISCOVERY
# ---------------------------------------------------------

def doctor_results(
    db: Session,
    specialisations: list[str],
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius: float = 20,
    query: str | None = None,
):
    stmt = (
        select(DoctorProfile)
        .options(
            joinedload(DoctorProfile.user),
            joinedload(DoctorProfile.chambers),
        )
        .where(
            DoctorProfile.verification_status == "verified"
        )
    )

    doctors = db.scalars(stmt).unique().all()

    results = []
    search_name = query.strip().casefold() if query else None

    for doctor in doctors:

        if not doctor.user:
            continue

        # Search doctor by name (case-insensitive partial match)
        if search_name and search_name not in doctor.user.full_name.casefold():
            continue

        doctor_specs = [
            item.strip().lower()
            for item in (doctor.specialisations or "").split(",")
        ]

        # Filter by specialisation
        if specialisations and not any(
            spec.strip().lower() in doctor_specs
            for spec in specialisations
        ):
            continue

        for chamber in doctor.chambers:

            if not chamber.active:
                continue

            if city and city.lower() not in (
                chamber.city or ""
            ).lower():
                continue

            distance = None

            if (
                lat is not None
                and lon is not None
                and chamber.latitude is not None
                and chamber.longitude is not None
            ):
                distance = haversine_km(
                    lat,
                    lon,
                    chamber.latitude,
                    chamber.longitude,
                )

                if distance > radius:
                    continue

            results.append(
                {
                    "doctor_id": doctor.id,
                    "name": doctor.user.full_name,
                    "specialisations": doctor.specialisations,
                    "experience_years": doctor.experience_years,
                    "chamber_id": chamber.id,
                    "chamber_name": chamber.name,
                    "address": chamber.address,
                    "city": chamber.city,
                    "distance_km": (
                        round(distance, 2)
                        if distance is not None
                        else None
                    ),
                }
            )

    if lat is not None and lon is not None:
        results.sort(
            key=lambda item: (
                item["distance_km"]
                if item["distance_km"] is not None
                else 10**9
            )
        )

    return results


# ---------------------------------------------------------
# AVAILABLE APPOINTMENT SLOTS
# ---------------------------------------------------------

def get_available_slots(
    db: Session,
    chamber: Chamber,
    service: DoctorService,
    target_date: date,
):

    schedule = db.scalar(
        select(Availability).where(
            Availability.chamber_id == chamber.id,
            Availability.weekday == target_date.weekday(),
            Availability.active.is_(True),
        )
    )

    if not schedule:
        return []

    start = datetime.combine(
        target_date,
        schedule.start_time,
    )

    end = datetime.combine(
        target_date,
        schedule.end_time,
    )

    duration = timedelta(
        minutes=service.duration_minutes
    )

    break_start = (
        datetime.combine(target_date, schedule.break_start)
        if schedule.break_start
        else None
    )

    break_end = (
        datetime.combine(target_date, schedule.break_end)
        if schedule.break_end
        else None
    )

    existing = db.scalars(
        select(Appointment).where(
            Appointment.chamber_id == chamber.id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(["confirmed", "pending"]),
        )
    ).all()

    slots = []
    cursor = start

    while cursor + duration <= end:

        slot_end = cursor + duration

        in_break = (
            break_start
            and break_end
            and cursor < break_end
            and slot_end > break_start
        )

        conflict = any(
            cursor < item.ends_at.replace(tzinfo=None)
            and slot_end > item.starts_at.replace(tzinfo=None)
            for item in existing
        )

        if not in_break and not conflict:
            slots.append(
                cursor.isoformat(timespec="minutes")
            )

        cursor += duration

    return slots


# ---------------------------------------------------------
# APPOINTMENT BOOKING
# ---------------------------------------------------------

def create_appointment(
    db: Session,
    patient: PatientProfile,
    payload: AppointmentCreate,
):

    chamber = db.scalar(
        select(Chamber)
        .where(
            Chamber.id == payload.chamber_id,
            Chamber.doctor_id == payload.doctor_id,
            Chamber.active.is_(True),
        )
        .with_for_update()
    )

    if not chamber:
        raise HTTPException(
            404,
            "Active chamber not found",
        )

    doctor = db.get(
        DoctorProfile,
        payload.doctor_id,
    )

    if (
        not doctor
        or doctor.verification_status != "verified"
    ):
        raise HTTPException(
            400,
            "Doctor is not verified and bookable",
        )

    service = db.scalar(
        select(DoctorService).where(
            DoctorService.id == payload.service_id,
            DoctorService.chamber_id == chamber.id,
            DoctorService.active.is_(True),
        )
    )

    if not service:
        raise HTTPException(
            404,
            "Active service not found for this chamber",
        )

    india_tz = ZoneInfo("Asia/Kolkata")

    starts = payload.starts_at

    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=india_tz)
    else:
        starts = starts.astimezone(india_tz)

    ends = starts + timedelta(
        minutes=service.duration_minutes
    )

    day = starts.date()

    local_start = starts.replace(tzinfo=None)
    local_end = ends.replace(tzinfo=None)

    schedule = db.scalar(
        select(Availability).where(
            Availability.chamber_id == chamber.id,
            Availability.weekday == day.weekday(),
            Availability.active.is_(True),
        )
    )

    if not schedule:
        raise HTTPException(
            400,
            "Doctor is not available on this date",
        )

    if not (
        schedule.start_time <= local_start.time()
        and local_end.time() <= schedule.end_time
    ):
        raise HTTPException(
            400,
            "Requested time is outside working hours",
        )

    if (
        schedule.break_start
        and schedule.break_end
        and local_start.time() < schedule.break_end
        and local_end.time() > schedule.break_start
    ):
        raise HTTPException(
            400,
            "Requested time overlaps a break",
        )

    conflict = db.scalar(
        select(Appointment)
        .where(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "pending"]),
            Appointment.starts_at < ends,
            Appointment.ends_at > starts,
        )
        .with_for_update()
    )

    if conflict:
        raise HTTPException(
            409,
            "This appointment time is no longer available",
        )

    counter = db.scalar(
        select(QueueCounter)
        .where(
            QueueCounter.doctor_id == doctor.id,
            QueueCounter.chamber_id == chamber.id,
            QueueCounter.queue_date == day,
        )
        .with_for_update()
    )

    if not counter:

        counter = QueueCounter(
            doctor_id=doctor.id,
            chamber_id=chamber.id,
            queue_date=day,
            last_number=0,
        )

        db.add(counter)
        db.flush()

    counter.last_number += 1

    token = f"{counter.last_number:03d}"

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        chamber_id=chamber.id,
        service_id=service.id,
        appointment_date=day,
        starts_at=starts,
        ends_at=ends,
        queue_token=token,
        status="confirmed",
    )

    db.add(appointment)
    db.flush()

    doctor_user = db.get(
        User,
        doctor.user_id,
    )

    if doctor_user is None:
        raise HTTPException(
            500,
            "Doctor account is missing",
        )

    notify(
        db,
        patient.user_id,
        "Appointment confirmed",
        f"Your appointment is confirmed. Queue token: {token}.",
    )

    notify(
        db,
        doctor_user.id,
        "New appointment",
        f"A new appointment has been booked. Queue token: {token}.",
    )

    return appointment, token
