"""
Run once to seed the database with therapists and sample data.
Usage: python -m app.seed
"""
from app.database import SessionLocal, create_tables
from app.models.models import Therapist, User
from services.auth_service import hash_password


THERAPISTS = [
    dict(name="Dr. Priya Sharma",   specialization="Stress, Burnout & Work-Life Balance",
         languages="English,Tamil",  approaches="CBT,Mindfulness",
         rating=4.9, review_count=124, availability="online", avatar_emoji="👩‍⚕️",
         bio="10 years experience helping professionals manage stress and regain balance."),
    dict(name="Dr. Arjun Nair",     specialization="Anxiety, Panic Disorders & Trauma",
         languages="English,Hindi",  approaches="DBT,EMDR",
         rating=4.8, review_count=87, availability="busy", avatar_emoji="👨‍⚕️",
         bio="Specialises in trauma recovery and anxiety management using evidence-based therapies."),
    dict(name="Dr. Meera Krishnan", specialization="Depression, Grief & Relationship Issues",
         languages="Tamil,English",  approaches="ACT,Psychotherapy",
         rating=4.7, review_count=63, availability="online", avatar_emoji="👩‍⚕️",
         bio="Compassionate therapist focused on helping clients navigate grief and low mood."),
    dict(name="Dr. Karan Mehta",    specialization="Youth, Teens & Academic Pressure",
         languages="English,Hindi",  approaches="Play Therapy,CBT",
         rating=5.0, review_count=41, availability="online", avatar_emoji="👨‍⚕️",
         bio="Dedicated to supporting young people through academic stress and life transitions."),
    dict(name="Dr. Lakshmi Rajan",  specialization="Women's Health & Postpartum Support",
         languages="Tamil,Telugu",   approaches="Feminist Therapy,Psychotherapy",
         rating=4.9, review_count=98, availability="busy", avatar_emoji="👩‍⚕️",
         bio="Specialist in women's mental health, postpartum depression, and trauma."),
    dict(name="Dr. Samuel Thomas",  specialization="Addiction Recovery & Self-Harm",
         languages="English,Malayalam", approaches="MI,CBT",
         rating=4.6, review_count=55, availability="offline", avatar_emoji="👨‍⚕️",
         bio="Recovery specialist with 15+ years working in addiction and self-harm recovery."),
]


def seed():
    create_tables()
    db = SessionLocal()
    try:
        # Seed therapists (skip if already exist)
        existing = db.query(Therapist).count()
        if existing == 0:
            for t in THERAPISTS:
                db.add(Therapist(**t))
            db.commit()
            print(f"✅ Seeded {len(THERAPISTS)} therapists")
        else:
            print(f"ℹ️  Therapists already seeded ({existing} found)")

        # Create a demo user for testing
        demo_email = "demo@solace.app"
        if not db.query(User).filter(User.email == demo_email).first():
            demo = User(
                email           = demo_email,
                display_name    = "Demo User",
                hashed_password = hash_password("Demo@1234"),
                is_anonymous    = False,
                is_active       = True,
                is_verified     = True,
            )
            db.add(demo)
            db.commit()
            print(f"✅ Demo user created: {demo_email} / Demo@1234")
        else:
            print("ℹ️  Demo user already exists")

    finally:
        db.close()
    print("🌙 Database seeding complete!")


if __name__ == "__main__":
    seed()
