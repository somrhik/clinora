# 🩺 Clinora

### A Doctor Discovery & Appointment Booking Platform

Discover doctors, explore their profiles, and manage appointments — all in one place.

<p align="center">
  <a href="https://clinora-theta.vercel.app/">
    🌐 **Live Demo — Clinora**
  </a>
</p>

---

## ✨ Overview

**Clinora** is a doctor discovery and appointment booking platform designed to simplify how patients find healthcare professionals and manage consultations.

The platform connects patients and doctors through an organised system for doctor discovery, professional profiles, appointment scheduling, and doctor verification.

## 🚀 Features

### 👤 Patient
- Patient registration and login.
- Personal profile management.
- Search and discover doctors.
- Explore doctor profiles, specialisations and consultation details.
- Book and manage appointments.
- View appointment history.
- Queue token generation.
- Patient report management with controlled access.

### 👨‍⚕️ Doctor
- Separate doctor registration and login.
- Professional profile management.
- Qualifications and experience details.
- Medical credential submission.
- Multiple chamber management.
- Consultation services and fee management.
- Availability and appointment management.
- Doctor verification workflow.

### 🛡️ Administration
- Doctor credential review.
- Doctor verification and approval.
- Administrative oversight of platform records.

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Routing | React Router |
| API Integration | Axios |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Migrations | Alembic |
| Authentication | JWT |
| Deployment | Vercel |

## 📁 Project Structure

```text
clinora/
│
├── backend/
│   ├── app/
│   ├── migrations/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── vercel.json
└── README.md
```

## ⚙️ Getting Started

### Prerequisites

- Python
- Node.js and npm
- PostgreSQL
- Git

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd clinora
```

### 2. Backend Setup

```bash
cd backend
```

Create a virtual environment:

**Windows:**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside the backend directory using `.env.example` as a reference. Configure your PostgreSQL connection and required environment variables.

Run database migrations:

```bash
python -m alembic upgrade head
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

Backend API: `http://127.0.0.1:8000`

API Documentation: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## 🌍 Live Deployment

Visit the deployed application:

**🔗 https://clinora-theta.vercel.app/**

## 🔐 Environment Variables

The backend requires environment-specific configuration for:

- PostgreSQL database connection.
- Authentication and security secrets.
- Frontend URL and CORS configuration.
- Google authentication (if enabled).
- SMTP configuration for password reset (if enabled).
- File storage configuration.

**Important:** Never commit `.env` files, passwords, API keys, authentication secrets, or private user documents to GitHub.

## 🧪 Development & Testing

Frontend production build:

```bash
cd frontend
npm run build
```

Backend API testing and interactive documentation are available through FastAPI Swagger UI.

## 🔮 Future Improvements

Clinora is under active development. Planned improvements include:

- Enhanced doctor discovery and filtering.
- Improved appointment management.
- More comprehensive profile management.
- UI/UX refinements.
- Additional security and deployment improvements.

## ⚠️ Disclaimer

Clinora is a doctor discovery and appointment management platform. It does not provide medical diagnosis or replace professional medical advice.

The application is currently under development and should not be used to handle real patient medical records until its security, privacy, and compliance requirements have been properly reviewed.

## 👨‍💻 Author

**Somrhik Banerjee**

---

<p align="center">
  💙 Built with passion to make doctor discovery and appointment booking simpler.
</p>