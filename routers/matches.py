from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, time
import pytz
import sqlalchemy
from database import get_db, models, schemas
from dependencies import get_current_active_user, get_current_admin_user

router = APIRouter(prefix="/api", tags=["matches", "predictions"])

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def get_current_vn_time():
    return datetime.now(VN_TZ)

# In-memory cache for country data to avoid heavy blob loading
COUNTRY_CACHE = {} 

def get_country_data(db: Session):
    global COUNTRY_CACHE
    if not COUNTRY_CACHE:
        print("Loading country data into cache...")
        countries = db.query(models.Country).all()
        # Cache stores: {code: (flag, name_vn)}
        COUNTRY_CACHE = {c.code.lower(): (c.flag_data, c.name_vn) for c in countries}
    return COUNTRY_CACHE

@router.get("/matches", response_model=List[schemas.MatchResponse])
def get_matches(db: Session = Depends(get_db)):
    # 1. Lấy năm hoạt động
    s_year = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    active_year = int(s_year.value) if s_year else 2026
    
    # 2. Lấy trận đấu kèm Odds trong 1 query (Eager Loading)
    matches = db.query(models.Match).options(
        joinedload(models.Match.odds)
    ).filter(models.Match.year == active_year).order_by(models.Match.start_time).all()
    
    # 3. Sử dụng Cache cho dữ liệu quốc gia
    c_data = get_country_data(db)
    
    # 4. Đếm số lượng bình luận cho từng trận đấu
    comment_counts = {m_id: count for m_id, count in db.query(models.Comment.match_id, sqlalchemy.func.count(models.Comment.id)).group_by(models.Comment.match_id).all()}
    
    res = []
    for m in matches:
        m_dict = schemas.MatchResponse.model_validate(m)
        m_dict.comment_count = comment_counts.get(m.id, 0)
        
        # Điền thông tin home team
        h_code = (m.home_team_code or "").lower()
        h_info = c_data.get(h_code, (None, None))
        m_dict.home_team_flag = h_info[0] or ""
        m_dict.home_team_vn = h_info[1] or m.home_team
        
        # Điền thông tin away team
        a_code = (m.away_team_code or "").lower()
        a_info = c_data.get(a_code, (None, None))
        m_dict.away_team_flag = a_info[0] or ""
        m_dict.away_team_vn = a_info[1] or m.away_team
        
        res.append(m_dict)
    return res

@router.get("/countries")
def get_countries(db: Session = Depends(get_db)):
    countries = db.query(models.Country).all()
    return [{"code": c.code, "name": c.name, "name_vn": c.name_vn} for c in countries]

@router.post("/predictions", response_model=schemas.PredictionResponse)
def submit_prediction(
    prediction_data: schemas.PredictionCreate, 
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    match = db.query(models.Match).filter(models.Match.id == prediction_data.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.locked or match.status != "READY":
        raise HTTPException(status_code=400, detail="Match is not ready or locked for predictions")
        
    if prediction_data.use_lucky_star and not match.lucky_star_enabled:
        raise HTTPException(status_code=400, detail="Ngôi sao may mắn chưa được kích hoạt cho trận này")
    
    # Check limit: before 7 PM UTC+7 on match day
    now_vn = get_current_vn_time()
    
    # ensure start_time is treated as timezone-aware for comparison, or naive but we know it's UTC+7 conceptually.
    # We will assume stored start_time is naive but represents UTC+7 time.
    match_start_vn = VN_TZ.localize(match.start_time) if match.start_time.tzinfo is None else match.start_time.astimezone(VN_TZ)
    
    # if today is match day, check if it's after 7 PM
    if now_vn.date() == match_start_vn.date() and now_vn.time() >= time(19, 0):
        raise HTTPException(status_code=400, detail="Prediction closed after 19:00 on match day")

    # Upsert prediction
    existing_prediction = db.query(models.Prediction).filter(
        models.Prediction.user_id == current_user.id,
        models.Prediction.match_id == match.id
    ).first()

    if existing_prediction:
        existing_prediction.chosen_team = prediction_data.chosen_team
        existing_prediction.use_lucky_star = prediction_data.use_lucky_star
    else:
        new_prediction = models.Prediction(
            user_id=current_user.id,
            match_id=match.id,
            chosen_team=prediction_data.chosen_team,
            use_lucky_star=prediction_data.use_lucky_star
        )
        db.add(new_prediction)
    
    db.commit()
    
    return existing_prediction if existing_prediction else new_prediction

@router.get("/predictions/match/{match_id}")
def get_match_predictions(match_id: int, current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get all predictions for a match (visible to all players)"""
    predictions = db.query(models.Prediction).filter(models.Prediction.match_id == match_id).all()
    # We only expose username/email and chosen team, not sensitive infos
    res = []
    for p in predictions:
        res.append({
            "user_email": p.user.email,
            "user_full_name": p.user.full_name,
            "chosen_team": p.chosen_team,
            "use_lucky_star": p.use_lucky_star,
            "is_me": p.user_id == current_user.id
        })
    return res

@router.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    # Get active year
    year_setting = db.query(models.Setting).filter_by(key="active_wc_year").first()
    active_year = int(year_setting.value) if year_setting else 2026

    # Get all users and their stats for this year
    # Use outer join to include users without stats records yet
    results = db.query(
        models.User,
        models.UserStats
    ).outerjoin(
        models.UserStats, 
        (models.UserStats.user_id == models.User.id) & (models.UserStats.year == active_year)
    ).filter(models.User.email != "admin@runsystem.net").all()
    
    def format_user(u, s):
        return {
            "email": u.email, 
            "full_name": u.full_name,
            "money_lost": s.money_lost if s else 0, 
            "total_correct": s.total_correct if s else 0, 
            "total_wrong": s.total_wrong if s else 0
        }

    formatted = [format_user(u, s) for u, s in results]
    # Sort by money_lost descending
    formatted.sort(key=lambda x: x["money_lost"], reverse=True)
    return formatted

from pydantic import BaseModel

class AdminPredictionUpdate(BaseModel):
    user_id: int
    match_id: int
    chosen_team: str

@router.post("/admin/predictions")
def admin_update_prediction(data: AdminPredictionUpdate, current_admin: models.User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    pred = db.query(models.Prediction).filter_by(user_id=data.user_id, match_id=data.match_id).first()
    if pred:
        pred.chosen_team = data.chosen_team
    else:
        new_pred = models.Prediction(user_id=data.user_id, match_id=data.match_id, chosen_team=data.chosen_team)
        db.add(new_pred)
    db.commit()
    return {"message": "Prediction updated by admin"}

@router.put("/admin/matches/{match_id}")
def admin_update_match(match_id: int, data: schemas.AdminMatchUpdate, current_admin: models.User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
        
    if data.home_team_code is not None: 
        match.home_team_code = data.home_team_code
        # Sync name from Country if not explicitly provided
        country = db.query(models.Country).filter_by(code=data.home_team_code).first()
        if country: match.home_team = country.name_vn or country.name

    if data.away_team_code is not None: 
        match.away_team_code = data.away_team_code
        country = db.query(models.Country).filter_by(code=data.away_team_code).first()
        if country: match.away_team = country.name_vn or country.name

    if data.home_team is not None: match.home_team = data.home_team
    if data.away_team is not None: match.away_team = data.away_team
    if data.stadium is not None: match.stadium = data.stadium
    if data.group_name is not None: match.group_name = data.group_name
    if data.start_time is not None: match.start_time = data.start_time
    if data.status is not None: match.status = data.status
    if data.locked is not None: match.locked = data.locked
    if data.lucky_star_enabled is not None: match.lucky_star_enabled = data.lucky_star_enabled
    if data.home_score is not None: match.home_score = data.home_score
    if data.away_score is not None: match.away_score = data.away_score
    
    odds = db.query(models.MatchOdds).filter(models.MatchOdds.match_id == match_id).first()
    if not odds and any([data.odds_favorite_team, data.odds_underdog_team, data.odds_handicap, data.odds_analysis_text]):
        odds = models.MatchOdds(match_id=match_id)
        db.add(odds)
        
    if odds:
        if data.odds_favorite_team is not None: odds.favorite_team = data.odds_favorite_team
        if data.odds_underdog_team is not None: odds.underdog_team = data.odds_underdog_team
        if data.odds_handicap is not None: odds.handicap = data.odds_handicap
        if data.odds_analysis_text is not None: odds.analysis_text = data.odds_analysis_text
        
    db.commit()
    return {"message": "Match updated successfully"}

from services.ai_service import generate_match_odds_and_analysis

@router.post("/admin/matches/{match_id}/generate-ai")
def admin_generate_ai_analysis(match_id: int, current_admin: models.User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
        
    # We fetch AI analysis but DO NOT save it yet, per user request "Show on UI first"
    ai_data = generate_match_odds_and_analysis(
        team1=match.home_team, 
        team2=match.away_team, 
        stage=match.stage, 
        stadium=match.stadium, 
        start_time=match.start_time.isoformat() if match.start_time else ""
    )
    return ai_data

# --- COMMENTS & REACTIONS ---

@router.get("/matches/{match_id}/comments", response_model=List[schemas.CommentResponse])
def get_match_comments(match_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    comments = db.query(models.Comment).filter(models.Comment.match_id == match_id).order_by(models.Comment.created_at.desc()).all()
    
    res = []
    for c in comments:
        # Group reactions
        reaction_counts = {}
        user_reactions = set()
        for r in c.reactions:
            reaction_counts[r.reaction_type] = reaction_counts.get(r.reaction_type, 0) + 1
            if r.user_id == current_user.id:
                user_reactions.add(r.reaction_type)
        
        stats = []
        for r_type, count in reaction_counts.items():
            stats.append(schemas.CommentReactionStats(
                reaction_type=r_type,
                count=count,
                user_reacted=r_type in user_reactions
            ))
            
        res.append(schemas.CommentResponse(
            id=c.id,
            match_id=c.match_id,
            user_id=c.user_id,
            user_full_name=c.user.full_name,
            user_email_prefix=c.user.email.split('@')[0],
            content=c.content,
            created_at=c.created_at,
            reactions=stats
        ))
    return res

@router.post("/matches/{match_id}/comments", response_model=schemas.CommentResponse)
def post_comment(match_id: int, comment_data: schemas.CommentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    new_comment = models.Comment(
        match_id=match_id,
        user_id=current_user.id,
        content=comment_data.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    
    return schemas.CommentResponse(
        id=new_comment.id,
        match_id=new_comment.match_id,
        user_id=new_comment.user_id,
        user_full_name=current_user.full_name,
        user_email_prefix=current_user.email.split('@')[0],
        content=new_comment.content,
        created_at=new_comment.created_at,
        reactions=[]
    )

@router.post("/comments/{comment_id}/react")
def toggle_reaction(comment_id: int, reaction_data: schemas.ReactionToggle, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    existing = db.query(models.CommentReaction).filter(
        models.CommentReaction.comment_id == comment_id,
        models.CommentReaction.user_id == current_user.id,
        models.CommentReaction.reaction_type == reaction_data.reaction_type
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        return {"message": "Reaction removed"}
    else:
        new_reaction = models.CommentReaction(
            comment_id=comment_id,
            user_id=current_user.id,
            reaction_type=reaction_data.reaction_type
        )
        db.add(new_reaction)
        db.commit()
        return {"message": "Reaction added"}

@router.put("/comments/{comment_id}")
def update_comment(comment_id: int, data: schemas.CommentUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bình luận.")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bạn không thể sửa bình luận của người khác.")
    
    comment.content = data.content
    db.commit()
    return {"message": "Đã cập nhật bình luận."}

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bình luận.")
    
    # Chỉ chủ sở hữu hoặc admin mới được xóa
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa bình luận này.")
    
    db.delete(comment)
    db.commit()
    return {"message": "Đã xóa bình luận."}
