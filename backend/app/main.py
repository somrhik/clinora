from pathlib import Path
from typing import Any, Literal, cast
import secrets

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, Response, Cookie

from fastapi.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import select

from sqlalchemy.orm import Session, joinedload

from app.config import settings

from app.database import Base, engine, get_db

from app.models import User, PatientProfile, DoctorProfile, Chamber, DoctorService, Availability, Appointment, MedicalReport, Notification, SymptomMapping, RefreshToken

from app.schemas import RegisterPatient, RegisterDoctor, LoginInput, ChamberCreate, ServiceCreate, AvailabilityCreate, AppointmentCreate, CancelInput, SymptomSearch, GeocodeInput

from app.security import hash_password, verify_password, create_access_token, create_refresh_token, hash_refresh_token, refresh_token_expiry, get_current_user, require_roles

from app.services import notify, emergency_matches, match_specialisations, doctor_results, get_available_slots, create_appointment, geocode_address, patient_address



from app.extensions import router as extensions_router

app = FastAPI(title=settings.app_name, version="1.0.0", description="Clinora doctor discovery and appointment management API")
COOKIE_SAMESITE = cast(Literal["lax", "strict", "none"], settings.refresh_cookie_samesite.lower())

app.include_router(extensions_router)

app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])



@app.get("/health")

def health():

    return {"status": "ok", "application": settings.app_name}



@app.post("/api/v1/auth/patient/register", status_code=201)

async def register_patient(payload: RegisterPatient, db: Session = Depends(get_db)):

    if db.scalar(select(User).where((User.email == payload.email) | (User.phone == payload.phone))):

        raise HTTPException(409, "Email or phone number is already registered")

    user = User(full_name=payload.full_name, email=payload.email, phone=payload.phone, password_hash=hash_password(payload.password), role="patient")

    db.add(user)

    db.flush()

    profile = PatientProfile(user_id=user.id, address=payload.address, locality=payload.locality, city=payload.city, state=payload.state, pin_code=payload.pin_code)
    db.add(profile)
    db.flush()
    location = None
    try:
        location = await geocode_address(patient_address(profile))
    except httpx.HTTPError:
        location = None
    if location:
        profile.latitude = location["latitude"]
        profile.longitude = location["longitude"]
    db.commit()
    return {"message": "Patient registered successfully", "user_id": user.id, "role": "patient", "location_saved": bool(location), "location_status": "geocoded" if location else "city_fallback"}



@app.post("/api/v1/auth/doctor/register", status_code=201)

def register_doctor(payload: RegisterDoctor, db: Session = Depends(get_db)):

    if db.scalar(select(User).where((User.email == payload.email) | (User.phone == payload.phone))):

        raise HTTPException(409, "Email or phone number is already registered")

    if db.scalar(select(DoctorProfile).where(DoctorProfile.registration_number == payload.registration_number)):

        raise HTTPException(409, "Medical registration number is already registered")

    user = User(full_name=payload.full_name, email=payload.email, phone=payload.phone, password_hash=hash_password(payload.password), role="doctor")

    db.add(user)

    db.flush()

    doctor = DoctorProfile(user_id=user.id, registration_number=payload.registration_number, qualifications=payload.qualifications, specialisations=payload.specialisations, experience_years=payload.experience_years, bio=payload.bio, graduation_year=payload.graduation_year, medical_college=payload.medical_college, previous_workplaces="\n".join(payload.previous_workplaces), verification_status="pending")

    db.add(doctor)

    db.commit()

    return {"message": "Doctor registration submitted for verification", "doctor_id": doctor.id, "verification_status": "pending"}



def login(payload: LoginInput, role: str, response: Response, db: Session):

    user = db.scalar(select(User).where(User.email == payload.email, User.role == role))

    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:

        raise HTTPException(401, "Invalid credentials")

    if role == "doctor":

        doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))

        if not doctor or doctor.verification_status in ["rejected", "suspended"]:

            raise HTTPException(403, "Doctor account is not permitted to sign in")

    raw_refresh_token = create_refresh_token()

    db.add(RefreshToken(user_id=user.id, token_hash=hash_refresh_token(raw_refresh_token), expires_at=refresh_token_expiry()))

    db.commit()

    response.set_cookie(

        key="refresh_token",

        value=raw_refresh_token,

        httponly=True,

        secure=settings.refresh_cookie_secure,

        samesite=COOKIE_SAMESITE,

        max_age=settings.refresh_token_days * 24 * 60 * 60,

        path="/api/v1/auth",

    )

    return {"access_token": create_access_token(user), "token_type": "bearer", "expires_in": settings.access_token_minutes * 60, "role": user.role, "user_id": user.id}



@app.post("/api/v1/auth/patient/login")

def patient_login(payload: LoginInput, response: Response, db: Session = Depends(get_db)):

    return login(payload, "patient", response, db)



@app.post("/api/v1/auth/doctor/login")

def doctor_login(payload: LoginInput, response: Response, db: Session = Depends(get_db)):

    return login(payload, "doctor", response, db)



@app.post("/api/v1/auth/admin/login")

def admin_login(payload: LoginInput, response: Response, db: Session = Depends(get_db)):

    return login(payload, "admin", response, db)



@app.post("/api/v1/auth/refresh")

def refresh_access_token(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):

    if not refresh_token:

        raise HTTPException(401, "Refresh token is missing")

    token_hash = hash_refresh_token(refresh_token)

    stored_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update())

    now = datetime.now(timezone.utc)

    if not stored_token or stored_token.revoked_at is not None or stored_token.expires_at <= now:

        raise HTTPException(401, "Refresh token is invalid or expired")

    account = db.get(User, stored_token.user_id)

    if not account or not account.is_active:

        stored_token.revoked_at = now

        db.commit()

        raise HTTPException(401, "Account is inactive")

    stored_token.revoked_at = now

    new_raw_token = create_refresh_token()

    db.add(RefreshToken(user_id=account.id, token_hash=hash_refresh_token(new_raw_token), expires_at=refresh_token_expiry()))

    db.commit()

    response.set_cookie(

        key="refresh_token",

        value=new_raw_token,

        httponly=True,

        secure=settings.refresh_cookie_secure,

        samesite=COOKIE_SAMESITE,

        max_age=settings.refresh_token_days * 24 * 60 * 60,

        path="/api/v1/auth",

    )

    return {"access_token": create_access_token(account), "token_type": "bearer", "expires_in": settings.access_token_minutes * 60, "role": account.role, "user_id": account.id}



@app.post("/api/v1/auth/logout")

def logout(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):

    if refresh_token:

        stored_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token)).with_for_update())

        if stored_token and stored_token.revoked_at is None:

            stored_token.revoked_at = datetime.now(timezone.utc)

            db.commit()

    response.delete_cookie(key="refresh_token", path="/api/v1/auth", httponly=True, secure=settings.refresh_cookie_secure, samesite=COOKIE_SAMESITE)

    return {"message": "Logged out successfully"}



@app.get("/api/v1/users/me")

def me(user: User = Depends(get_current_user)):

    return {"id": user.id, "full_name": user.full_name, "email": user.email, "phone": user.phone, "role": user.role}



@app.get("/api/v1/patients/me")

def patient_profile(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):

    profile = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))
    if profile is None:
        raise HTTPException(404, "Patient profile not found")

    return {"user": {"id": user.id, "full_name": user.full_name, "email": user.email, "phone": user.phone}, "profile": profile}



@app.get("/api/v1/doctors/me")

def doctor_profile(user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):

    doctor = cast(Any, db.scalar(select(DoctorProfile).options(joinedload(DoctorProfile.chambers)).where(DoctorProfile.user_id == user.id)))

    return {"doctor_id": doctor.id, "name": user.full_name, "email": user.email, "phone": user.phone, "registration_number": doctor.registration_number, "qualifications": doctor.qualifications, "specialisations": doctor.specialisations, "experience_years": doctor.experience_years, "bio": doctor.bio, "graduation_year": doctor.graduation_year, "medical_college": doctor.medical_college, "previous_workplaces": doctor.previous_workplaces.splitlines() if doctor.previous_workplaces else [], "verification_status": doctor.verification_status, "rejection_reason": doctor.rejection_reason, "chambers": [{"id": c.id, "name": c.name, "city": c.city} for c in doctor.chambers]}



@app.post("/api/v1/doctors/chambers", status_code=201)

async def create_chamber(payload: ChamberCreate, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):

    doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))
    if doctor is None:
        raise HTTPException(404, "Doctor profile not found")

    chamber_data = payload.model_dump(exclude={"id"})
    address = ", ".join(part for part in [payload.address, payload.locality, payload.city, payload.state, payload.pin_code, "India"] if part)
    location = None
    try:
        location = await geocode_address(address)
    except httpx.HTTPError:
        location = None
    if location:
        chamber_data["latitude"] = location["latitude"]
        chamber_data["longitude"] = location["longitude"]
    chamber = Chamber(doctor_id=doctor.id, **chamber_data)
    db.add(chamber)
    db.commit()
    db.refresh(chamber)
    return {"id": chamber.id, "name": chamber.name, "city": chamber.city, "location_saved": bool(location)}



@app.post("/api/v1/doctors/services", status_code=201)

def create_service(payload: ServiceCreate, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):

    doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))
    if doctor is None:
        raise HTTPException(404, "Doctor profile not found")

    chamber = db.scalar(select(Chamber).where(Chamber.id == payload.chamber_id, Chamber.doctor_id == doctor.id))

    if not chamber:

        raise HTTPException(404, "Chamber not found")

    service = DoctorService(**payload.model_dump())

    db.add(service)

    db.commit()

    db.refresh(service)

    return {"id": service.id, "name": service.name, "fee": float(service.fee), "duration_minutes": service.duration_minutes}



@app.post("/api/v1/doctors/availability", status_code=201)

def set_availability(payload: AvailabilityCreate, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):

    doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))
    if doctor is None:
        raise HTTPException(404, "Doctor profile not found")

    chamber = db.scalar(select(Chamber).where(Chamber.id == payload.chamber_id, Chamber.doctor_id == doctor.id))

    if not chamber:

        raise HTTPException(404, "Chamber not found")

    if payload.end_time <= payload.start_time:

        raise HTTPException(400, "End time must be after start time")

    item = Availability(**payload.model_dump())

    db.add(item)

    db.commit()

    db.refresh(item)

    return {"id": item.id, "weekday": item.weekday, "start_time": str(item.start_time), "end_time": str(item.end_time)}




@app.get("/api/v1/doctors/search")
def search_doctors(
    query: str | None = None,
    specialisation: str | None = None,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db)
):
    patient = db.scalar(
        select(PatientProfile).where(PatientProfile.user_id == user.id)
    )

    if patient is None:
        raise HTTPException(404, "Patient profile not found")

    specs = [specialisation] if specialisation else []

    results = doctor_results(
        db,
        specs,
        city=patient.city if patient.latitude is None or patient.longitude is None else None,
        lat=patient.latitude,
        lon=patient.longitude,
        radius=20,
        query=query
    )

    return {
        "results": results,
        "location_source": "saved_patient_profile",
        "radius_km": 20
    }

@app.post("/api/v1/symptoms/search")
def symptom_search(payload: SymptomSearch, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    emergencies = emergency_matches(payload.symptoms)
    if emergencies:
        return {"emergency_warning": True, "is_diagnosis": False, "message": "Your symptoms may require urgent medical attention. Do not delay emergency care to book a routine appointment. In India, call 112 for emergency assistance.", "matched_warning_signs": emergencies, "suggested_specialisations": [], "doctors": []}
    patient = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    if patient is None:
        raise HTTPException(404, "Patient profile not found")
    specialisations = match_specialisations(db, payload.symptoms)
    results = doctor_results(db, specialisations, city=patient.city if patient.latitude is None or patient.longitude is None else None, lat=patient.latitude, lon=patient.longitude, radius=20)
    return {"emergency_warning": False, "is_diagnosis": False, "message": "These are doctor-discovery suggestions, not a diagnosis.", "suggested_specialisations": specialisations, "doctors": results, "location_source": "saved_patient_profile", "radius_km": 20}


@app.get("/api/v1/doctors/nearby")
def nearby_doctors(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    patient = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    if patient is None:
        raise HTTPException(404, "Patient profile not found")
    if not patient.city and (patient.latitude is None or patient.longitude is None):
        raise HTTPException(400, "Add your address to your patient profile before searching nearby doctors")
    results = doctor_results(db, [], city=patient.city if patient.latitude is None else None, lat=patient.latitude, lon=patient.longitude, radius=20)
    return {"results": results, "location_source": "saved_patient_profile", "radius_km": 20}


@app.post("/api/v1/location/geocode")
async def geocode_saved_patient_location(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    patient = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    if patient is None:
        raise HTTPException(404, "Patient profile not found")
    try:
        location = await geocode_address(patient_address(patient))
    except httpx.HTTPError:
        location = None
    if not location:
        raise HTTPException(503, "Saved address could not be geocoded. Check the address and Google Maps API configuration.")
    patient.latitude = location["latitude"]
    patient.longitude = location["longitude"]
    db.commit()
    return {"latitude": patient.latitude, "longitude": patient.longitude, "formatted_address": location["formatted_address"], "message": "Patient location saved successfully"}


@app.get("/api/v1/appointments/available-slots")

def available_slots(chamber_id: int, service_id: int, target_date: date, db: Session = Depends(get_db)):

    chamber = db.get(Chamber, chamber_id)

    service = db.get(DoctorService, service_id)

    if not chamber or not service or service.chamber_id != chamber.id:

        raise HTTPException(404, "Chamber or service not found")

    if not chamber.active or not service.active:

        raise HTTPException(400, "Chamber or service is inactive")

    return {"date": target_date.isoformat(), "slots": get_available_slots(db, chamber, service, target_date)}



@app.post("/api/v1/appointments/book", status_code=201)

def book_appointment(payload: AppointmentCreate, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):

    patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))
    if patient is None:
        raise HTTPException(404, "Patient profile not found")

    try:

        appointment, token = create_appointment(db, patient, payload)

        db.commit()

    except Exception:

        db.rollback()

        raise

    return {"message": "Appointment booked successfully", "appointment_id": appointment.id, "queue_token": token, "queue_position": int(token), "status": appointment.status, "starts_at": appointment.starts_at.isoformat()}



@app.get("/api/v1/appointments/my")

def my_appointments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    if user.role == "patient":

        patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))
        if patient is None:
            raise HTTPException(404, "Patient profile not found")

        items = db.scalars(select(Appointment).where(Appointment.patient_id == patient.id).order_by(Appointment.starts_at.desc())).all()

    elif user.role == "doctor":

        doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))
        if doctor is None:
            raise HTTPException(404, "Doctor profile not found")

        items = db.scalars(select(Appointment).where(Appointment.doctor_id == doctor.id).order_by(Appointment.starts_at.desc())).all()

    else:

        raise HTTPException(403, "Not available for administrator accounts")

    return [{"id": a.id, "date": a.appointment_date, "starts_at": a.starts_at, "queue_token": a.queue_token, "status": a.status, "doctor_id": a.doctor_id, "chamber_id": a.chamber_id} for a in items]



@app.post("/api/v1/appointments/{appointment_id}/cancel")

def cancel_appointment(appointment_id: int, payload: CancelInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    appointment = db.get(Appointment, appointment_id)

    if not appointment:

        raise HTTPException(404, "Appointment not found")

    allowed = False

    if user.role == "patient":

        patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))

        allowed = bool(patient and appointment.patient_id == patient.id)

    if user.role == "doctor":

        doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))

        allowed = bool(doctor and appointment.doctor_id == doctor.id)

    if not allowed:

        raise HTTPException(403, "You cannot cancel this appointment")

    if appointment.status != "confirmed":

        raise HTTPException(400, "Only confirmed appointments can be cancelled")

    appointment.status = "cancelled"

    appointment.cancellation_reason = payload.reason

    db.commit()

    return {"message": "Appointment cancelled", "queue_token": appointment.queue_token}



@app.post("/api/v1/reports/upload", status_code=201)

async def upload_report(appointment_id: int, shared_with_doctor: bool = False, file: UploadFile = File(...), user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):

    patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))

    if patient is None:
        raise HTTPException(404, "Patient profile not found")

    appointment = db.scalar(select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == patient.id))

    if not appointment:

        raise HTTPException(404, "Patient appointment not found")

    allowed_types = {"application/pdf", "image/jpeg", "image/png"}

    if file.content_type not in allowed_types:

        raise HTTPException(400, "Only PDF, JPEG and PNG files are allowed")

    content = await file.read()

    if len(content) > settings.max_upload_mb * 1024 * 1024:

        raise HTTPException(413, "File exceeds the configured upload limit")

    directory = Path(settings.upload_dir)

    directory.mkdir(parents=True, exist_ok=True)

    stored_name = f"report_{patient.id}_{appointment.id}_{secrets.token_hex(12)}"

    (directory / stored_name).write_bytes(content)

    report = MedicalReport(patient_id=patient.id, appointment_id=appointment.id, original_filename=file.filename or "report", stored_filename=stored_name, content_type=file.content_type, shared_with_doctor=shared_with_doctor)

    db.add(report)

    db.commit()

    db.refresh(report)

    return {"id": report.id, "filename": report.original_filename, "shared_with_doctor": report.shared_with_doctor}



@app.get("/api/v1/reports/{report_id}/download")

def download_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    report = db.get(MedicalReport, report_id)

    if not report:

        raise HTTPException(404, "Report not found")

    permitted = False

    if user.role == "patient":

        patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))

        permitted = bool(patient and report.patient_id == patient.id)

    elif user.role == "doctor":

        doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))

        appointment = db.get(Appointment, report.appointment_id)

        permitted = bool(doctor and appointment and appointment.doctor_id == doctor.id and report.shared_with_doctor)

    if not permitted:

        raise HTTPException(403, "You are not authorized to download this report")

    path = Path(settings.upload_dir) / report.stored_filename

    if not path.exists():

        raise HTTPException(404, "Stored report file is missing")

    return FileResponse(path, media_type=report.content_type, filename=report.original_filename)



@app.get("/api/v1/reports/my")

def my_reports(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):

    patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))

    if patient is None:
        raise HTTPException(404, "Patient profile not found")

    reports = db.scalars(select(MedicalReport).where(MedicalReport.patient_id == patient.id)).all()

    return [{"id": r.id, "appointment_id": r.appointment_id, "filename": r.original_filename, "shared_with_doctor": r.shared_with_doctor, "created_at": r.created_at} for r in reports]



@app.get("/api/v1/appointments/{appointment_id}/reports")

def appointment_reports(appointment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    appointment = db.get(Appointment, appointment_id)

    if not appointment:

        raise HTTPException(404, "Appointment not found")

    permitted = False

    if user.role == "patient":

        patient = cast(Any, db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id)))

        permitted = bool(patient and appointment.patient_id == patient.id)

    elif user.role == "doctor":

        doctor = cast(Any, db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id)))

        permitted = bool(doctor and appointment.doctor_id == doctor.id)

    if not permitted:

        raise HTTPException(403, "Not authorized")

    query = select(MedicalReport).where(MedicalReport.appointment_id == appointment_id)

    if user.role == "doctor":

        query = query.where(MedicalReport.shared_with_doctor.is_(True))

    reports = db.scalars(query).all()

    return [{"id": r.id, "filename": r.original_filename, "shared_with_doctor": r.shared_with_doctor} for r in reports]



@app.get("/api/v1/notifications")

def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    items = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())).all()

    return [{"id": n.id, "title": n.title, "message": n.message, "read": n.read, "created_at": n.created_at} for n in items]



@app.get("/api/v1/admin/doctors/pending")

def pending_doctors(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):

    doctors = db.scalars(select(DoctorProfile).options(joinedload(DoctorProfile.user)).where(DoctorProfile.verification_status == "pending")).unique().all()

    return [{"doctor_id": d.id, "name": d.user.full_name, "email": d.user.email, "registration_number": d.registration_number, "qualifications": d.qualifications, "specialisations": d.specialisations} for d in doctors]



@app.post("/api/v1/admin/doctors/{doctor_id}/verify")

def verify_doctor(doctor_id: int, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):

    doctor = db.get(DoctorProfile, doctor_id)

    if not doctor:

        raise HTTPException(404, "Doctor not found")

    doctor.verification_status = "verified"

    doctor.rejection_reason = None

    notify(db, doctor.user_id, "Doctor verification approved", "Your Clinora doctor profile has been verified.")

    db.commit()

    return {"message": "Doctor verified", "doctor_id": doctor.id}



@app.post("/api/v1/admin/doctors/{doctor_id}/reject")

def reject_doctor(doctor_id: int, reason: str, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):

    doctor = db.get(DoctorProfile, doctor_id)

    if not doctor:

        raise HTTPException(404, "Doctor not found")

    doctor.verification_status = "rejected"

    doctor.rejection_reason = reason

    notify(db, doctor.user_id, "Doctor verification rejected", reason)

    db.commit()

    return {"message": "Doctor registration rejected"}



@app.post("/api/v1/admin/users/{user_id}/status")

def set_user_status(user_id: int, active: bool, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):

    target = db.get(User, user_id)

    if not target or target.role == "admin":

        raise HTTPException(404, "User not found")

    target.is_active = active

    db.commit()

    return {"user_id": target.id, "is_active": target.is_active}
