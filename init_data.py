import os
from dotenv import load_dotenv

# Load environment variables from Render secrets path if it exists, otherwise from .env
render_secrets_path = "/etc/secrets/.env"
if os.path.exists(render_secrets_path):
    load_dotenv(render_secrets_path)
else:
    load_dotenv()

import json
from datetime import datetime
from database import engine, SessionLocal, Base, models

def reset_database():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    try:
        # 1. Seed Countries from wiki/countries.json
        print("Loading countries from wiki/countries.json...")
        countries_file = "wiki/countries.json"
        if os.path.exists(countries_file):
            with open(countries_file, "r", encoding="utf-8") as f:
                countries_data = json.load(f)
                for c in countries_data:
                    code = c["code"].lower()
                    # Skip if exists
                    existing = db.query(models.Country).filter_by(code=code).first()
                    if not existing:
                        db.add(models.Country(
                            code=code,
                            name=c["name"],
                            name_vn=c.get("name_vn"),
                            flag_data=c.get("flag_data", "")
                        ))
            db.commit()
            print("Countries seeded.")

        # 2. Insert Settings
        db.add(models.Setting(key="penalty_per_loss", value="20000"))
        db.add(models.Setting(key="lucky_star_amount", value="300000"))
        db.add(models.Setting(key="default_prediction_time", value="19:00"))
        
        # 3. Create Admin User
        from services.auth import get_password_hash
        admin_user = models.User(
            email="admin@runsystem.net",
            full_name="Admin",
            password_hash=get_password_hash("admin123"),
            is_active=True,
            is_admin=True
        )
        db.add(admin_user)
        db.commit()
        print("Data initialized successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error initializing data: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    reset_database()
    seed_data()
