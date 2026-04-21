import os
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
        
        # 2. Seed Stadiums from JSON matches
        print("Extracting stadiums from wiki files...")
        stadium_info = {} # Key: name, Value: {city, country}
        with open("wiki/matchs-scheduled.json", "r", encoding="utf-8") as fs:
            ko_data = json.load(fs)
            for km in ko_data.get("matches", []):
                sname = km["venue"]["stadium"]
                if sname not in stadium_info:
                    stadium_info[sname] = {
                        "city": km["venue"].get("city"),
                        "country": km["venue"].get("country")
                    }
        
        for sname, info in stadium_info.items():
            db.add(models.Stadium(
                name=sname, 
                city=info["city"], 
                country=info["country"]
            ))
        db.commit()
        print(f"Seeded {len(stadium_info)} stadiums.")

        # 3. Insert Settings
        db.add(models.Setting(key="penalty_per_loss", value="20000"))
        db.add(models.Setting(key="lucky_star_amount", value="300000"))
        db.add(models.Setting(key="default_prediction_time", value="19:00"))
        
        # 4. Create Admin User
        from services.auth import get_password_hash
        admin_user = models.User(
            email="admin@runsystem.net",
            full_name="Admin",
            password_hash=get_password_hash("admin123"),
            is_active=True,
            is_admin=True
        )
        db.add(admin_user)

        # 5. Seed Matches from matches.json
        print("Loading matches from wiki/matchs-scheduled.json...")
        with open("wiki/matchs-scheduled.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for m in data.get("matches", []):
            try:
                # the json datetime format is DD/MM/YYYY HH:MM
                start_dt = datetime.strptime(m["datetime"], "%d/%m/%Y %H:%M")
            except ValueError:
                start_dt = datetime.now() # fallback
                
            api_match_id = f"WC26-{m['match']:03d}"
            
            new_match = models.Match(
                year=2026,
                match_no=m['match'],
                api_match_id=api_match_id,
                stage=f"Group {m['group']}" if m.get("group") else "Knockout",
                home_team=m["team1"]["name"],
                home_team_code=m["team1"]["code"],
                away_team=m["team2"]["name"],
                away_team_code=m["team2"]["code"],
                start_time=start_dt,
                stadium=m["venue"]["stadium"],
                status="SCHEDULED",
                lucky_star_enabled=False
            )
            db.add(new_match)
            db.flush() # get ID
            
            # Simple mock odds
            db.add(models.MatchOdds(
                match_id=new_match.id,
                handicap=0.5,
                favorite_team=m["team1"]["name"],
                underdog_team=m["team2"]["name"],
                analysis_text=f"Phân tích AI: {m['team1']['name']} vs {m['team2']['name']}. "
                              f"Trận đấu diễn ra tại {m['venue']['stadium']}."
            ))

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
