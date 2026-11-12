# Clinora

**A doctor discovery and appointment booking platform.**

Clinora is a web application designed to help patients discover doctors,
explore consultation options, and manage appointments. Doctors can
create professional profiles, manage their chambers and availability,
and handle appointment requests. The platform also includes a
verification workflow for doctor credentials.

> **Project status:** Development / initial deployment. Features and
> workflows are still being tested and improved. Clinora is not a
> diagnostic tool and does not replace professional medical advice.

## Overview

Clinora aims to make the process of finding and booking a doctor more
organised through a single platform.

### Patient features

-   Patient registration and login.
-   Patient profile management.
-   Doctor discovery by name, speciality, and relevant search criteria.
-   Doctor profile and consultation information.
-   Appointment booking and appointment management.
-   Queue token generation for booked appointments.
-   Patient reports support, with access intended to be controlled by
    the patient.

### Doctor features

-   Separate doctor registration and login.
-   Professional profile with qualifications and experience.
-   Medical registration and credential submission.
-   Multiple chamber details and consultation services.
-   Availability and appointment management.
-   Doctor verification workflow.

### Administration

-   Doctor credential review and verification.
-   Administrative oversight of platform records and verification
    status.

*The exact availability of individual features may vary while
development and testing continue.*

## Tech Stack

### Frontend

-   React
-   TypeScript
-   Vite
-   React Router
-   Axios
-   React Hook Form / Zod
-   Lucide React

### Backend

-   Python
-   FastAPI
-   SQLAlchemy
-   Pydantic
-   Alembic
-   JWT-based authentication

### Database

-   PostgreSQL

## Project Structure

``` text
clinora/
├── backend/
│   ├── app/
│   ├── migrations/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Run Locally

### Prerequisites

Install the following before running the project:

-   Python 3.11 or a compatible version supported by the backend
    dependencies.
-   Node.js and npm.
-   PostgreSQL.
-   Git (optional, for cloning the repository).

### 1. Clone the repository

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd clinora
```

### 2. Configure the backend

Open a terminal in the project directory:

``` bash
cd backend
```

Create and activate a virtual environment.

**Windows PowerShell:**

``` powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

``` bash
pip install -r requirements.txt
```

Create a `.env` file inside the `backend/` directory, using
`.env.example` as a reference. Update the values for your local
PostgreSQL database and other required settings.

Do not commit `.env` or put passwords, secret keys, API keys, or other
credentials in source control.

Run database migrations:

``` bash
python -m alembic upgrade head
```

Start the backend:

``` bash
uvicorn app.main:app --reload
```

The backend will normally be available at:

-   API: http://127.0.0.1:8000
-   Swagger documentation: http://127.0.0.1:8000/docs

### 3. Configure the frontend

Open a **second terminal** from the project root:

``` bash
cd frontend
npm install
```

Start the Vite development server:

``` bash
npm run dev
```

Vite will print the local frontend URL in the terminal, usually:

-   http://localhost:5173

Keep both the backend and frontend terminals running while using the
local application.

## Environment Configuration

The backend reads its configuration from `backend/.env`. Use
`backend/.env.example` as the source of the required variable names.

Typical configuration areas include:

-   PostgreSQL connection URL.
-   JWT/authentication secrets and token settings.
-   Frontend base URL and allowed CORS origins.
-   Google authentication client ID, if Google sign-in is enabled.
-   SMTP settings, if email-based password reset is enabled.
-   Application timezone.
-   Private upload/storage configuration for doctor documents and
    patient reports.

Use strong, unique secrets outside local development. Configure
production values in your hosting provider's environment-variable
settings rather than uploading a `.env` file.

## API Documentation

When the backend is running, FastAPI provides interactive API
documentation at:

``` text
http://127.0.0.1:8000/docs
```

Use Swagger UI to inspect available endpoints and test API requests
during development.

## Testing and Build Checks

### Frontend production build

From the `frontend/` directory:

``` bash
npm run build
```

### Backend

Activate the backend virtual environment and run the checks or tests
available in the repository. Database-backed tests should use a separate
test database, not a database containing important development or
production data.

## Deployment

The application can be deployed as separate frontend, backend, and
PostgreSQL services. Before deployment:

1.  Provision a cloud PostgreSQL database.
2.  Configure backend environment variables securely.
3.  Run Alembic migrations against the intended cloud database.
4.  Deploy the FastAPI backend.
5.  Configure CORS and the frontend API base URL.
6.  Deploy the React frontend.
7.  Configure persistent, private storage for uploaded documents and
    reports.

Do not use temporary application filesystems for documents that must
remain available after a redeploy or restart.

## Privacy and Medical Disclaimer

Clinora is intended for doctor discovery and appointment management. It
does not provide medical diagnosis or emergency care.

Do not upload real patient records or sensitive medical documents to an
unreviewed demo deployment. Before handling real patient information,
review authentication, authorisation, access controls, file storage,
encryption, logging, backups, and applicable privacy and healthcare
requirements.

In an emergency, contact local emergency services rather than relying on
this platform.

## Contributing

This project is under active development. Contributions, issue reports,
and suggestions are welcome.

For changes:

1.  Create a branch for your work.
2.  Make and test your changes locally.
3.  Ensure secrets and private data are not included.
4.  Submit a pull request describing the changes.

## Author

**Somrhik Banerjee**

------------------------------------------------------------------------

*Clinora --- simplifying doctor discovery and appointment management.*
