from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db, models, schemas
from dependencies import get_current_active_user, get_current_admin_user
from datetime import datetime

router = APIRouter(prefix="/api/tournament", tags=["tournament"])

@router.get("/summary", response_model=schemas.TournamentStatus)
def get_tournament_summary(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    # 1. Lấy năm hoạt động
    s_year = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    active_year = int(s_year.value) if s_year else 2026
    
    # 2. Lấy kết quả giải đấu (tạo mới nếu chưa có)
    result = db.query(models.TournamentResult).filter(models.TournamentResult.year == active_year).first()
    if not result:
        result = models.TournamentResult(year=active_year)
        db.add(result)
        db.commit()
        db.refresh(result)
    
    # 3. Lấy dự đoán
    votes = db.query(models.TournamentVote).filter(models.TournamentVote.year == active_year).all()
    
    # Lấy cài đặt phí
    s_champ_fee = db.query(models.Setting).filter(models.Setting.key == "tournament_champion_fee").first()
    s_play_fee = db.query(models.Setting).filter(models.Setting.key == "tournament_player_fee").first()
    champ_fee = int(s_champ_fee.value) if s_champ_fee else 20000
    play_fee = int(s_play_fee.value) if s_play_fee else 20000

    # Tính pool (nên dùng sum của fee_paid để chính xác nếu admin đổi fee giữa chừng)
    champion_pool = db.query(func.sum(models.TournamentVote.fee_paid)).filter(
        models.TournamentVote.year == active_year,
        models.TournamentVote.category == "CHAMPION"
    ).scalar() or 0
    
    player_pool = db.query(func.sum(models.TournamentVote.fee_paid)).filter(
        models.TournamentVote.year == active_year,
        models.TournamentVote.category == "BEST_PLAYER"
    ).scalar() or 0
    
    # Format response
    all_votes_res = []
    for v in votes:
        u = db.query(models.User).filter(models.User.id == v.user_id).first()
        all_votes_res.append(schemas.TournamentVoteResponse(
            id=v.id,
            user_id=v.user_id,
            user_full_name=u.full_name if u else "Unknown",
            category=v.category,
            selection=v.selection,
            fee_paid=v.fee_paid
        ))
    
    user_votes = [v for v in all_votes_res if v.user_id == current_user.id]
    
    return schemas.TournamentStatus(
        year=active_year,
        champion_locked=result.champion_locked,
        player_locked=result.player_locked,
        is_finalized=result.is_finalized,
        champion_pool=champion_pool,
        player_pool=player_pool,
        champion_fee=champ_fee,
        player_fee=play_fee,
        user_votes=user_votes,
        all_votes=all_votes_res
    )

@router.post("/vote")
def submit_vote(vote_data: schemas.TournamentVoteCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    if current_user.email == "admin@runsystem.net":
        raise HTTPException(status_code=403, detail="Tài khoản admin không được phép tham gia bình chọn.")
        
    s_year = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    active_year = int(s_year.value) if s_year else 2026
    
    result = db.query(models.TournamentResult).filter(models.TournamentResult.year == active_year).first()
    if not result:
        raise HTTPException(status_code=404, detail="Tournament result record not found")
    
    if vote_data.category == "CHAMPION" and result.champion_locked:
        raise HTTPException(status_code=400, detail="Bình chọn đội vô địch đã bị khóa")
    if vote_data.category == "BEST_PLAYER" and result.player_locked:
        raise HTTPException(status_code=400, detail="Bình chọn cầu thủ đã bị khóa")
    
    # Check existing vote
    existing = db.query(models.TournamentVote).filter(
        models.TournamentVote.user_id == current_user.id,
        models.TournamentVote.year == active_year,
        models.TournamentVote.category == vote_data.category
    ).first()
    
    if existing:
        existing.selection = vote_data.selection
        db.commit()
        return {"message": "Cập nhật dự đoán thành công"}
    
    # First time: charge fee from settings
    s_champ_fee = db.query(models.Setting).filter(models.Setting.key == "tournament_champion_fee").first()
    s_play_fee = db.query(models.Setting).filter(models.Setting.key == "tournament_player_fee").first()
    champ_fee = int(s_champ_fee.value) if s_champ_fee else 20000
    play_fee = int(s_play_fee.value) if s_play_fee else 20000
    
    current_fee = champ_fee if vote_data.category == "CHAMPION" else play_fee

    stats = db.query(models.UserStats).filter(
        models.UserStats.user_id == current_user.id,
        models.UserStats.year == active_year
    ).first()
    if not stats:
        stats = models.UserStats(user_id=current_user.id, year=active_year)
        db.add(stats)
    
    stats.tournament_money_lost = (stats.tournament_money_lost or 0) + current_fee
    
    new_vote = models.TournamentVote(
        user_id=current_user.id,
        year=active_year,
        category=vote_data.category,
        selection=vote_data.selection,
        fee_paid=current_fee
    )
    db.add(new_vote)
    db.commit()
    return {"message": f"Đã ghi nhận dự đoán và trừ phí tham gia {current_fee:,} DU1"}

@router.post("/admin/settings")
def update_tournament_settings(data: schemas.TournamentResultUpdate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin_user)):
    s_year = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    active_year = int(s_year.value) if s_year else 2026
    
    result = db.query(models.TournamentResult).filter(models.TournamentResult.year == active_year).first()
    if not result:
        result = models.TournamentResult(year=active_year)
        db.add(result)
    
    if data.champion_result is not None: result.champion_result = data.champion_result
    if data.player_result is not None: result.player_result = data.player_result
    if data.champion_locked is not None: result.champion_locked = data.champion_locked
    if data.player_locked is not None: result.player_locked = data.player_locked
    
    db.commit()
    return {"message": "Cập nhật cấu hình thành công"}

@router.post("/admin/finalize")
def finalize_tournament(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin_user)):
    s_year = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    active_year = int(s_year.value) if s_year else 2026
    
    result = db.query(models.TournamentResult).filter(models.TournamentResult.year == active_year).first()
    if not result or result.is_finalized:
        raise HTTPException(status_code=400, detail="Đã quyết toán hoặc không tìm thấy thông tin")
    
    if not result.champion_result or not result.player_result:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đầy đủ kết quả trước khi quyết toán")

    # Finalize categories independently
    for cat, res_val in [("CHAMPION", result.champion_result), ("BEST_PLAYER", result.player_result)]:
        votes = db.query(models.TournamentVote).filter(
            models.TournamentVote.year == active_year,
            models.TournamentVote.category == cat
        ).all()
        
        if not votes: continue
        
        total_pool = sum(v.fee_paid for v in votes)
        # Case insensitive compare
        winners = [v for v in votes if v.selection.strip().lower() == res_val.strip().lower()]
        
        if not winners:
            # Refund everyone for this category
            for v in votes:
                stats = db.query(models.UserStats).filter(models.UserStats.user_id == v.user_id, models.UserStats.year == active_year).first()
                if stats: stats.tournament_money_lost = (stats.tournament_money_lost or 0) - v.fee_paid
        else:
            # Distribute prize
            reward = total_pool // len(winners)
            for v in winners:
                stats = db.query(models.UserStats).filter(models.UserStats.user_id == v.user_id, models.UserStats.year == active_year).first()
                if stats: stats.tournament_money_lost = (stats.tournament_money_lost or 0) - reward # reward reduces debt

    result.is_finalized = True
    db.commit()
    return {"message": "Đã quyết toán thành công và cập nhật quỹ thưởng cho người thắng cuộc"}

# --- PLAYER CANDIDATES ---
@router.get("/player-candidates", response_model=List[schemas.TournamentPlayerCandidateResponse])
def get_player_candidates(db: Session = Depends(get_db)):
        
    s_year = db.query(models.Setting).filter(models.Setting.key == "active_wc_year").first()
    active_year = int(s_year.value) if s_year else 2026
    return db.query(models.TournamentPlayerCandidate).filter(models.TournamentPlayerCandidate.year == active_year).all()

@router.post("/admin/player-candidates", response_model=schemas.TournamentPlayerCandidateResponse)
def add_player_candidate(data: schemas.TournamentPlayerCandidateCreate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin_user)):
    new_p = models.TournamentPlayerCandidate(**data.model_dump())
    db.add(new_p)
    db.commit()
    db.refresh(new_p)
    return new_p

@router.delete("/admin/player-candidates/{p_id}")
def delete_player_candidate(p_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin_user)):
    p = db.query(models.TournamentPlayerCandidate).filter(models.TournamentPlayerCandidate.id == p_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")
    db.delete(p)
    db.commit()
    return {"message": "Đã xóa cầu thủ khỏi danh sách gợi ý"}
