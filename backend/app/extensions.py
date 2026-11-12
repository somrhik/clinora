
from pathlib import Path
from typing import Literal, cast
from datetime import datetime, timezone, timedelta
import hashlib
import secrets
import smtplib
from email.message import EmailMessage

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Query,
    Response,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    User,
    PatientProfile,
    DoctorProfile,
    DoctorDocument,
    PasswordResetToken,
    RefreshToken,
    Appointment,
)
from app.schemas import (
    ForgotPasswordInput,
    ResetPasswordInput,
    GoogleAuthInput,
    PatientProfileUpdate,
    DoctorProfileUpdate,
    AppointmentCreate,
)
from app.security import (
    hash_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    require_roles,
)
from app.services import geocode_address, patient_address, create_appointment


router = APIRouter()


def send_reset_email(email: str, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from_email:
        return False

    msg = EmailMessage()
    msg["Subject"] = "Reset your Clinora password"
    msg["From"] = settings.smtp_from_email
    msg["To"] = email
    msg.set_content(
        f"Reset your password within {settings.password_reset_minutes} "
        f"minutes: {settings.frontend_base_url}/reset-password?token={token}"
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)

    return True


@router.post("/api/v1/auth/forgot-password")
def forgot_password(
    payload: ForgotPasswordInput,
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == payload.email))

    result: dict[str, str | bool] = {
        "message": "If that email is registered, password reset instructions will be sent."
    }

    if not user:
        return result

    now = datetime.now(timezone.utc)

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now})

    raw = secrets.token_urlsafe(40)

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
        )
    )

    db.commit()

    try:
        sent = send_reset_email(user.email, raw)
    except Exception:
        sent = False

    if settings.environment == "development" and not sent:
        result.update(
            {
                "development_reset_token": raw,
                "email_configured": False,
            }
        )

    return result


@router.post("/api/v1/auth/reset-password")
def reset_password(
    payload: ResetPasswordInput,
    db: Session = Depends(get_db),
):
    digest = hashlib.sha256(payload.token.encode()).hexdigest()

    record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == digest)
        .with_for_update()
    )

    now = datetime.now(timezone.utc)

    if (
        not record
        or record.used_at is not None
        or record.expires_at <= now
    ):
        raise HTTPException(400, "Reset link is invalid or expired")

    user = db.get(User, record.user_id)

    if not user:
        raise HTTPException(400, "Reset link is invalid or expired")

    user.password_hash = hash_password(payload.new_password)
    record.used_at = now

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now})

    db.commit()

    return {"message": "Password updated. Please sign in again."}


@router.post("/api/v1/auth/google")
async def google_sign_in(
    payload: GoogleAuthInput,
    response: Response,
    db: Session = Depends(get_db),
):
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": payload.credential},
        )

    if r.status_code != 200:
        raise HTTPException(401, "Google credential is invalid")

    claims = r.json()

    if (
        claims.get("aud") != settings.google_client_id
        or claims.get("email_verified") != "true"
    ):
        raise HTTPException(401, "Google account could not be verified")

    email = claims["email"].lower()
    user = db.scalar(select(User).where(User.email == email))

    if user and user.role != "patient":
        raise HTTPException(
            409,
            "This email belongs to another account type. Use regular sign-in.",
        )

    if not user:
        user = User(
            full_name=claims.get("name") or email.split("@")[0],
            email=email,
            phone=f"google-{secrets.token_hex(12)}",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="patient",
        )

        db.add(user)
        db.flush()
        db.add(PatientProfile(user_id=user.id))

    if not user.is_active:
        raise HTTPException(403, "Account is inactive")

    raw = create_refresh_token()

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            expires_at=refresh_token_expiry(),
        )
    )

    db.commit()

    response.set_cookie(
        "refresh_token",
        raw,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=cast(
            Literal["lax", "strict", "none"],
            settings.refresh_cookie_samesite,
        ),
        max_age=settings.refresh_token_days * 86400,
        path="/api/v1/auth",
    )

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "role": user.role,
        "user_id": user.id,
    }


@router.patch("/api/v1/patients/me")
async def update_patient(
    payload: PatientProfileUpdate,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    profile = db.scalar(
        select(PatientProfile).where(PatientProfile.user_id == user.id)
    )

    if not profile:
        raise HTTPException(404, "Patient profile not found")

    data = payload.model_dump(exclude_unset=True)

    if "phone" in data and db.scalar(
        select(User).where(
            User.phone == data["phone"],
            User.id != user.id,
        )
    ):
        raise HTTPException(409, "Phone number is already registered")

    for key in ("full_name", "phone"):
        if key in data:
            setattr(user, key, data.pop(key))

    for key, value in data.items():
        setattr(profile, key, value)

    if any(
        key in data
        for key in ("address", "locality", "city", "state", "pin_code")
    ):
        try:
            loc = await geocode_address(patient_address(profile))
            if loc:
                profile.latitude = loc["latitude"]
                profile.longitude = loc["longitude"]
        except httpx.HTTPError:
            pass

    db.commit()

    return {
        "message": "Patient profile updated",
        "location_saved": (
            profile.latitude is not None
            and profile.longitude is not None
        ),
    }


@router.patch("/api/v1/doctors/me")
def update_doctor(
    payload: DoctorProfileUpdate,
    user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
):
    doctor = db.scalar(
        select(DoctorProfile).where(DoctorProfile.user_id == user.id)
    )

    if not doctor:
        raise HTTPException(404, "Doctor profile not found")

    data = payload.model_dump(exclude_unset=True)

    if "phone" in data and db.scalar(
        select(User).where(
            User.phone == data["phone"],
            User.id != user.id,
        )
    ):
        raise HTTPException(409, "Phone number is already registered")

    if "previous_workplaces" in data:
        data["previous_workplaces"] = "\n".join(
            data["previous_workplaces"] or []
        )

    for key in ("full_name", "phone"):
        if key in data:
            setattr(user, key, data.pop(key))

    for key, value in data.items():
        setattr(doctor, key, value)

    db.commit()

    return {
        "message": "Doctor profile updated",
        "verification_status": doctor.verification_status,
    }


@router.post("/api/v1/doctors/documents", status_code=201)
async def upload_doctor_document(
    document_type: str = Query(..., min_length=2, max_length=80),
    file: UploadFile = File(...),
    user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
):
    doctor = db.scalar(
        select(DoctorProfile).where(DoctorProfile.user_id == user.id)
    )

    if not doctor:
        raise HTTPException(404, "Doctor profile not found")

    if file.content_type not in {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }:
        raise HTTPException(415, "Only PDF, JPEG and PNG files are accepted")

    content = await file.read()

    if not content or len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            413,
            f"File must not exceed {settings.max_upload_mb} MB",
        )

    stored = (
        f"doctor_{doctor.id}_{secrets.token_hex(16)}"
        f"{Path(file.filename or 'file').suffix.lower()}"
    )

    folder = Path(settings.upload_dir) / "doctor_documents"
    folder.mkdir(parents=True, exist_ok=True)

    (folder / stored).write_bytes(content)

    doc = DoctorDocument(
        doctor_id=doctor.id,
        document_type=document_type.strip(),
        original_filename=Path(file.filename or "document").name,
        stored_filename=stored,
        content_type=file.content_type,
    )

    db.add(doc)
    db.commit()

    return {
        "id": doc.id,
        "document_type": doc.document_type,
        "filename": doc.original_filename,
        "message": "Document uploaded securely",
    }


@router.get("/api/v1/doctors/documents")
def own_doctor_documents(
    user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
):
    doctor = db.scalar(
        select(DoctorProfile).where(DoctorProfile.user_id == user.id)
    )

    if not doctor:
        raise HTTPException(404, "Doctor profile not found")

    docs = db.scalars(
        select(DoctorDocument).where(
            DoctorDocument.doctor_id == doctor.id
        )
    ).all()

    return [
        {
            "id": doc.id,
            "document_type": doc.document_type,
            "filename": doc.original_filename,
            "uploaded_at": doc.uploaded_at,
        }
        for doc in docs
    ]


@router.get("/api/v1/admin/doctors/{doctor_id}/documents")
def admin_doctor_documents(
    doctor_id: int,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    docs = db.scalars(
        select(DoctorDocument).where(
            DoctorDocument.doctor_id == doctor_id
        )
    ).all()

    return [
        {
            "id": doc.id,
            "document_type": doc.document_type,
            "filename": doc.original_filename,
            "uploaded_at": doc.uploaded_at,
        }
        for doc in docs
    ]


@router.get("/api/v1/admin/doctor-documents/{document_id}/download")
def admin_download_document(
    document_id: int,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    doc = db.get(DoctorDocument, document_id)

    if not doc:
        raise HTTPException(404, "Document not found")

    path = (
        Path(settings.upload_dir)
        / "doctor_documents"
        / doc.stored_filename
    )

    if not path.is_file():
        raise HTTPException(404, "Stored document not found")

    return FileResponse(
        path,
        media_type=doc.content_type,
        filename=doc.original_filename,
    )


@router.post("/api/v1/appointments/{appointment_id}/repeat", status_code=201)
def repeat_booking(
    appointment_id: int,
    starts_at: datetime,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    patient = db.scalar(
        select(PatientProfile).where(PatientProfile.user_id == user.id)
    )

    previous = db.get(Appointment, appointment_id)

    if (
        not patient
        or not previous
        or previous.patient_id != patient.id
    ):
        raise HTTPException(404, "Previous appointment not found")

    payload = AppointmentCreate(
        doctor_id=previous.doctor_id,
        chamber_id=previous.chamber_id,
        service_id=previous.service_id,
        starts_at=starts_at,
    )

    try:
        created, token = create_appointment(db, patient, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {
        "message": "Repeat appointment booked successfully",
        "appointment_id": created.id,
        "queue_token": token,
        "status": created.status,
    }
