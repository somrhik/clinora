import argparse
from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app.models import User, SymptomMapping
from app.security import hash_password

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-phone", required=True)
    parser.add_argument("--admin-name", default="Clinora Administrator")
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == args.admin_email)):
            raise SystemExit("An account with this email already exists")
        admin = User(full_name=args.admin_name, email=args.admin_email, phone=args.admin_phone, password_hash=hash_password(args.admin_password), role="admin")
        db.add(admin)
        defaults = {
            "rash": "Dermatology", "itching": "Dermatology", "skin": "Dermatology",
            "palpitations": "Cardiology", "heart": "Cardiology", "blurred vision": "Ophthalmology",
            "toothache": "Dentistry", "joint pain": "Orthopaedics", "headache": "Neurology",
            "cough": "Pulmonology", "digestive": "Gastroenterology", "diabetes": "Endocrinology",
            "ear": "ENT", "throat": "ENT"
        }
        for keyword, speciality in defaults.items():
            db.add(SymptomMapping(keyword=keyword, specialisation=speciality))
        db.commit()
        print("Administrator created and initial symptom mappings seeded.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
