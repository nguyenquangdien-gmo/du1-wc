from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from database import get_db, models, schemas
from dependencies import get_current_admin_user
from services import scheduler

router = APIRouter(prefix="/api/admin", tags=["admin"])

# --- USER MANAGEMENT ---
@router.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    return db.query(models.User).all()

@router.get("/active-year")
def get_active_year(db: Session = Depends(get_db)):
    s = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    return {"year": int(s.value) if s else 2026}

@router.put("/users/{user_id}")
def update_user_admin(user_id: int, data: schemas.UserAdminUpdate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.is_active is not None: user.is_active = data.is_active
    if data.is_admin is not None: user.is_admin = data.is_admin
    
    db.commit()
    return {"message": "User updated"}

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Bạn không thể tự xóa chính mình.")
        
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    
    # Xóa dữ liệu liên quan
    db.query(models.Prediction).filter(models.Prediction.user_id == user_id).delete()
    db.query(models.UserStats).filter(models.UserStats.user_id == user_id).delete()
    db.query(models.OTP).filter(models.OTP.email == user.email).delete()
    
    db.delete(user)
    db.commit()
    return {"message": "Đã xóa người dùng thành công."}

@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    
    import secrets
    import string
    from services.auth import get_password_hash
    from services.email_service import send_password_reset_email_async

    # Generate random 8-character password
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for _ in range(8))
    
    user.password_hash = get_password_hash(new_password)
    db.commit()
    
    # Send email notification
    send_password_reset_email_async(user.email, new_password)
    
    return {"message": f"Đã reset mật khẩu cho {user.email} thành công. Mật khẩu mới đã được gửi qua email."}

# --- COUNTRY MANAGEMENT ---
@router.get("/countries", response_model=List[schemas.CountryResponse])
def get_all_countries_admin(db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    return db.query(models.Country).all()

@router.put("/countries/{code}")
def update_country_admin(code: str, data: schemas.CountryUpdate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    c = db.query(models.Country).filter(models.Country.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Country not found")
    c.name_vn = data.name_vn
    db.commit()
    return {"message": "Country updated"}

# --- STADIUM MANAGEMENT ---
@router.get("/stadiums", response_model=List[schemas.StadiumResponse])
def get_stadiums(db: Session = Depends(get_db)):
    return db.query(models.Stadium).all()

@router.post("/stadiums")
def create_stadium(data: schemas.StadiumUpdate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    new_s = models.Stadium(name=data.name, city=data.city)
    db.add(new_s)
    db.commit()
    return {"message": "Stadium added"}

@router.put("/stadiums/{s_id}")
def update_stadium(s_id: int, data: schemas.StadiumUpdate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    s = db.query(models.Stadium).filter(models.Stadium.id == s_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Stadium not found")
    s.name = data.name
    s.city = data.city
    db.commit()
    return {"message": "Stadium updated"}

@router.delete("/stadiums/{s_id}")
def delete_stadium(s_id: int, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    s = db.query(models.Stadium).filter(models.Stadium.id == s_id).first()
    if s:
        db.delete(s)
        db.commit()
    return {"message": "Stadium deleted"}

# --- BATCH MANAGEMENT ---

@router.post("/batch/predict/run")
def run_batch_predict(current_admin: models.User = Depends(get_current_admin_user)):
    scheduler.run_batch_predict_manual()
    return {"message": "Predict Batch executed manually"}

@router.post("/batch/live/run")
def run_batch_live(current_admin: models.User = Depends(get_current_admin_user)):
    scheduler.run_batch_live_manual()
    return {"message": "Live Batch executed manually"}

# --- SETTINGS MANAGEMENT ---
@router.get("/settings")
def get_settings(db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    settings = db.query(models.Setting).all()
    return {s.key: s.value for s in settings}

@router.patch("/settings")
def update_settings(data: schemas.SettingUpdate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    if data.penalty_per_loss is not None:
        s = db.query(models.Setting).filter(models.Setting.key == "penalty_per_loss").first()
        if s: s.value = str(data.penalty_per_loss)
    
    if data.lucky_star_amount is not None:
        s = db.query(models.Setting).filter(models.Setting.key == "lucky_star_amount").first()
        if s: s.value = str(data.lucky_star_amount)

    if data.default_prediction_time is not None:
        s = db.query(models.Setting).filter(models.Setting.key == "default_prediction_time").first()
        if s: s.value = str(data.default_prediction_time)

    # Batch Settings
    batch_fields = [
        ('batch_predict_interval', data.batch_predict_interval),
        ('batch_predict_enabled', data.batch_predict_enabled),
        ('batch_predict_start_time', data.batch_predict_start_time),
        ('batch_live_interval', data.batch_live_interval),
        ('batch_live_enabled', data.batch_live_enabled),
        ('batch_live_start_time', data.batch_live_start_time),
        ('active_wc_year', data.active_wc_year),
    ]

    needs_sync = False
    for key, val in batch_fields:
        if val is not None:
            s = db.query(models.Setting).filter(models.Setting.key == key).first()
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            if not s:
                db.add(models.Setting(key=key, value=val_str))
            else:
                s.value = val_str
            needs_sync = True

    db.commit()
    if needs_sync:
        scheduler.sync_scheduler_settings()
    return {"message": "Settings updated"}

@router.post("/years/create-from-file")
async def create_new_wc_year_from_file(
    file: UploadFile = File(...),
    year: int = Form(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin_user)
):
    if (year - 2022) % 4 != 0:
        raise HTTPException(status_code=400, detail=f"Năm {year} không phải là năm diễn ra World Cup")

    from services.ai_service import extract_matches_from_file
    import os
    import time

    safe_filename = f"temp_upload_{int(time.time())}{os.path.splitext(file.filename)[1]}"
    temp_path = f"wiki/{safe_filename}"
    os.makedirs("wiki", exist_ok=True)
    
    print(f"Saving temporary upload to {temp_path}...")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        print(f"Extracting data for WC {year} from uploaded file (File API mode)...")
        tournament_data = extract_matches_from_file(temp_path, year)
    finally:
        if os.path.exists(temp_path):
            print(f"Removing temporary local file: {temp_path}")
            os.remove(temp_path)
    
    if not tournament_data or "matches" not in tournament_data:
        raise HTTPException(status_code=500, detail="AI không thể trích xuất dữ liệu từ file này hoặc định dạng không hợp lệ.")
        
    return _process_tournament_import(db, year, tournament_data)

def _process_tournament_import(db: Session, year: int, tournament_data: dict):
    import json
    # Save to wiki files
    with open(f"wiki/matchs-scheduled_{year}.json", "w", encoding="utf-8") as f:
        json.dump(tournament_data, f, ensure_ascii=False, indent=2)
        
    # Import into DB
    s_active = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    if not s_active:
        db.add(models.Setting(key="active_wc_year", value=str(year)))
    else:
        s_active.value = str(year)
        
    from datetime import datetime
    for m in tournament_data.get("matches", []):
        try: dt = datetime.strptime(m["datetime"], "%d/%m/%Y %H:%M")
        except: dt = datetime.now()
        
        # Stadium handling
        venue = m.get("venue", {})
        stadium_name = venue.get("stadium", "Không xác định")
        stadium_city = venue.get("city", "")
        stadium_country = venue.get("country", "")
        
        # Check and insert stadium if not exists
        if stadium_name != "Không xác định":
            existing_stadium = db.query(models.Stadium).filter(models.Stadium.name == stadium_name).first()
            if not existing_stadium:
                new_stadium = models.Stadium(name=stadium_name, city=stadium_city, country=stadium_country)
                db.add(new_stadium)
                db.flush() 

        # Use round as stage, handle match numbering
        stage_label = m.get("round", "Vòng bảng")
        if m.get("group"):
            stage_label = f"{stage_label} - Bảng {m['group']}"

        match_obj = models.Match(
            year=year, 
            match_no=m["match"], 
            api_match_id=f"WC{str(year)[2:]}-{m['match']:03d}",
            stage=stage_label, 
            group_name=m.get("group"),
            home_team=m["team1"]["name"], 
            home_team_code=m["team1"].get("code"),
            away_team=m["team2"]["name"], 
            away_team_code=m["team2"].get("code"),
            start_time=dt, 
            stadium=stadium_name, 
            status="SCHEDULED"
        )
        db.add(match_obj)
        db.flush()
        
        # Initial Odds
        fav = match_obj.home_team
        under = match_obj.away_team
        if "Không xác định" in fav or "Không xác định" in under:
            fav = "TBD"
            under = "TBD"

        db.add(models.MatchOdds(
            match_id=match_obj.id, 
            handicap=0.0, 
            favorite_team=fav, 
            underdog_team=under, 
            analysis_text=f"{stage_label} - World Cup {year}"
        ))

    db.commit()
    return {"message": f"Đã tạo thành công dữ liệu World Cup {year}", "year": year}

@router.delete("/years/{year}")
def delete_wc_year(year: int, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin_user)):
    # Check if any match has started or finished
    active_matches = db.query(models.Match).filter(
        models.Match.year == year,
        (models.Match.status != "SCHEDULED") | (models.Match.home_score != None)
    ).first()
    
    if active_matches:
        raise HTTPException(status_code=400, detail=f"Không thể xóa năm {year} vì đã có trận đấu diễn ra hoặc đang diễn ra.")

    # Delete odds, predictions, then matches
    matches = db.query(models.Match).filter(models.Match.year == year).all()
    match_ids = [m.id for m in matches]
    
    db.query(models.MatchOdds).filter(models.MatchOdds.match_id.in_(match_ids)).delete(synchronize_session=False)
    db.query(models.Prediction).filter(models.Prediction.match_id.in_(match_ids)).delete(synchronize_session=False)
    db.query(models.Match).filter(models.Match.year == year).delete(synchronize_session=False)
    
    # Delete stats for that year
    db.query(models.UserStats).filter(models.UserStats.year == year).delete(synchronize_session=False)
    
    # Delete wiki file
    import os
    wiki_file = f"wiki/matchs-scheduled_{year}.json"
    if os.path.exists(wiki_file):
        os.remove(wiki_file)

    db.commit()
    return {"message": f"Đã xóa toàn bộ dữ liệu World Cup {year}"}
