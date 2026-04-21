import os
from dotenv import load_dotenv

# Load environment variables from Render secrets path if it exists, otherwise from .env
render_secrets_path = "/etc/secrets/.env"
if os.path.exists(render_secrets_path):
    load_dotenv(render_secrets_path)
else:
    load_dotenv()

import json
import logging
from datetime import datetime
from database import engine, SessionLocal, Base, models

# Cấu hình log để dễ dàng theo dõi trên Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    try:
        logger.info("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("Creating all tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database reset successful.")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise

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
        settings_to_seed = [
            {"key": "penalty_per_loss", "value": "20000"},
            {"key": "lucky_star_amount", "value": "300000"},
            {"key": "default_prediction_time", "value": "19:00"}
        ]
        for s in settings_to_seed:
            existing_setting = db.query(models.Setting).filter_by(key=s["key"]).first()
            if not existing_setting:
                db.add(models.Setting(key=s["key"], value=s["value"]))
        
        # 3. Create Admin User
        from services.auth import get_password_hash
        admin_email = "admin@runsystem.net"
        existing_admin = db.query(models.User).filter_by(email=admin_email).first()
        if not existing_admin:
            admin_user = models.User(
                email=admin_email,
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
