# Clinora Backend

FastAPI backend for Clinora. See the project-root README for setup, API workflows, integrations and limitations.


## New account and doctor-verification workflows

Apply the additive migration after updating the code:

```powershell
alembic upgrade head
```

New environment variables (copy from `.env.example`):
- `GOOGLE_CLIENT_ID`: Google Identity Services OAuth web client ID. Google sign-in is patient-only.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`: SMTP settings for password-reset email.
- `PASSWORD_RESET_MINUTES`: reset-token lifetime (default 20).
- `FRONTEND_BASE_URL`: public frontend origin used to construct reset links.

New endpoints:
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/google` (expects a Google ID credential)
- `PATCH /api/v1/patients/me`
- `PATCH /api/v1/doctors/me`
- `POST /api/v1/doctors/documents?document_type=...` (multipart `file`)
- `GET /api/v1/doctors/documents`
- Admin: `GET /api/v1/admin/doctors/{doctor_id}/documents`
- Admin: `GET /api/v1/admin/doctor-documents/{document_id}/download`

Doctor credentials now include medical college, optional graduation year and previous workplaces. Documents are stored under `UPLOAD_DIR/doctor_documents`, outside the public frontend. Only administrators can retrieve document downloads. Password-reset tokens are hashed, expire, are single-use, and invalidate refresh sessions when redeemed.

In development, if SMTP is not configured, the forgot-password response includes a temporary `development_reset_token` for local testing. This is intentionally disabled outside development. Configure SMTP before production.
