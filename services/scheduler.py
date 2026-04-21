from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from database import SessionLocal, models
from services.ai_service import simulate_match_live_update
from datetime import datetime, timedelta
import pytz

scheduler = BackgroundScheduler()
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def get_next_run_time(time_str: str):
    if not time_str: return None
    try:
        now = datetime.now(VN_TZ)
        h, m = map(int, time_str.split(':'))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target < now:
            # If time already passed today, start tomorrow
            target += timedelta(days=1)
        return target
    except Exception as e:
        print(f"Error parsing time {time_str}: {e}")
        return None

def init_settings():
    db = SessionLocal()
    try:
        defaults = {
            "lucky_star_amount": "300000",
            "penalty_per_loss": "10000",
            "default_prediction_time": "19:00",
            "batch_predict_interval": "1",
            "batch_predict_enabled": "true",
            "batch_predict_start_time": "19:00",
            "batch_live_interval": "5",
            "batch_live_enabled": "true",
            "batch_live_start_time": "19:00",
            "active_wc_year": "2026",
        }
        for k, v in defaults.items():
            if not db.query(models.Setting).filter(models.Setting.key == k).first():
                db.add(models.Setting(key=k, value=v))
        db.commit()
    finally:
        db.close()


def task_auto_default_prediction():
    """Run every minute to check if it's past 19:00 VN time on match day and default users"""
    db = get_db()
    now_vn = datetime.now(VN_TZ)
    
    # Get active users
    users = db.query(models.User).filter(models.User.is_active == True, models.User.email != "admin@runsystem.net").all()
    
    # Get matches today that are READY
    matches_today = []
    for match in db.query(models.Match).filter(models.Match.status == "READY").all():
        m_start = VN_TZ.localize(match.start_time) if match.start_time.tzinfo is None else match.start_time.astimezone(VN_TZ)
        if m_start.date() == now_vn.date():
            matches_today.append(match)
            
    if not matches_today: 
        db.close()
        return

    # Check settings for time
    time_setting = db.query(models.Setting).filter_by(key="default_prediction_time").first()
    limit_time_str = time_setting.value if time_setting else "19:00"
    hour, minute = map(int, limit_time_str.split(':'))
    limit_time = datetime.now(VN_TZ).replace(hour=hour, minute=minute, second=0, microsecond=0)

    if now_vn >= limit_time:
        for match in matches_today:
            if match.locked: continue
            
            match.locked = True # Lock predictions for this match
            
            # Find default team (highest handicap equivalent)
            default_team = match.odds.favorite_team if match.odds else match.home_team

            for user in users:
                pred = db.query(models.Prediction).filter_by(user_id=user.id, match_id=match.id).first()
                if not pred:
                    db.add(models.Prediction(
                        user_id=user.id,
                        match_id=match.id,
                        chosen_team=default_team,
                        use_lucky_star=False
                    ))
            db.commit()
    db.close()

def calculate_winner_asian_handicap(home_team, away_team, home_score, away_score, favorite_team, handicap):
    # Basic asian handicap logic
    if favorite_team == home_team:
        adjusted_home = home_score - handicap
        adjusted_away = away_score
    else:
        adjusted_home = home_score
        adjusted_away = away_score - handicap
        
    if adjusted_home > adjusted_away:
        return home_team
    elif adjusted_home < adjusted_away:
        return away_team
    else:
        return "DRAW"

def task_live_score_updater():
    """Runs every 5 minutes to update scores of LIVE matches, and start SCHEDULED matches that passed their start time"""
    db = get_db()
    now_vn = datetime.now(VN_TZ)

    # Start matches
    for match in db.query(models.Match).filter(models.Match.status == "SCHEDULED").all():
        m_start = VN_TZ.localize(match.start_time) if match.start_time.tzinfo is None else match.start_time.astimezone(VN_TZ)
        if now_vn >= m_start:
            match.status = "LIVE"
            match.home_score = 0
            match.away_score = 0
            db.commit()

    # Update matches
    live_matches = db.query(models.Match).filter(models.Match.status == "LIVE").all()
    for match in live_matches:
        update = simulate_match_live_update(match.home_team, match.away_team, match.home_score, match.away_score)
        match.home_score = update.get("home_score", match.home_score)
        match.away_score = update.get("away_score", match.away_score)
        
        if update.get("match_finished", False):
            match.status = "FINISHED"
            # Settle predictions
            settle_match(db, match)
            
        db.commit()
    db.close()

def settle_match(db: Session, match: models.Match):
    penalty_setting = db.query(models.Setting).filter_by(key="penalty_per_loss").first()
    penalty = int(penalty_setting.value) if penalty_setting else 20000
    
    lucky_star_setting = db.query(models.Setting).filter_by(key="lucky_star_amount").first()
    lucky_star_amount = int(lucky_star_setting.value) if lucky_star_setting else 300000
    
    odds = match.odds
    handicap = odds.handicap if odds else 0.0
    favorite = odds.favorite_team if odds else match.home_team
    
    winning_team_bet = calculate_winner_asian_handicap(match.home_team, match.away_team, match.home_score, match.away_score, favorite, handicap)
    
    predictions = db.query(models.Prediction).filter_by(match_id=match.id).all()
    for pred in predictions:
        # Get or create UserStats for this user and this year
        stats = db.query(models.UserStats).filter_by(user_id=pred.user_id, year=match.year).first()
        if not stats:
            stats = models.UserStats(user_id=pred.user_id, year=match.year)
            db.add(stats)
            db.flush()

        if winning_team_bet == "DRAW":
            pred.result = "DRAW"
            # Return money / no change
            pred.money_changed = 0
        else:
            if pred.chosen_team == winning_team_bet:
                pred.result = "WON"
                stats.total_correct += 1
                pred.money_changed = 0
                if pred.use_lucky_star:
                    pred.money_changed = -lucky_star_amount # -300k meaning debt decreases by 300k
            else:
                pred.result = "LOST"
                stats.total_wrong += 1
                pred.money_changed = penalty
                if pred.use_lucky_star:
                    pred.money_changed += lucky_star_amount # +300k meaning debt increases by 300k
            
        stats.money_lost += pred.money_changed
        
    db.commit()

    # Progress tournament if needed (simplistic logic)
    # E.g. If stage is Quarter-Final, we'd find/create Semi-Final match and update it.
    actual_winner = match.home_team if match.home_score > match.away_score else match.away_team
    # Tie breaking logic (penalties) is skipped for simplicity, assuming one always wins in knockouts.
    
    # A complete tree progression requires predefined tree structure. We'll leave it as a placeholder to be triggered.
    print(f"Settled match {match.home_team} vs {match.away_team}. Bet winner: {winning_team_bet}. Actual winner: {actual_winner}")


def run_batch_predict_manual():
    print(f"Manual Batch PREDICT triggered at {datetime.now(VN_TZ)}")
    task_auto_default_prediction()
    return True

def run_batch_live_manual():
    print(f"Manual Batch LIVE triggered at {datetime.now(VN_TZ)}")
    task_live_score_updater()
    return True

def sync_scheduler_settings():
    db = SessionLocal()
    try:
        settings = db.query(models.Setting).all()
        s_dict = {s.key: s.value for s in settings}
        

        # Sync Predict Job
        predict_interval = s_dict.get('batch_predict_interval', 1)
        predict_enabled = s_dict.get('batch_predict_enabled', 'true') == 'true'
        predict_start_time = s_dict.get('batch_predict_start_time', s_dict.get('default_prediction_time', '19:00'))
        
        job_predict = scheduler.get_job('batch_predict')
        if job_predict:
            scheduler.reschedule_job('batch_predict', trigger='interval', minutes=int(predict_interval), start_date=get_next_run_time(predict_start_time))
            if predict_enabled: scheduler.resume_job('batch_predict')
            else: scheduler.pause_job('batch_predict')
        else:
            scheduler.add_job(task_auto_default_prediction, 'interval', minutes=int(predict_interval), id='batch_predict', start_date=get_next_run_time(predict_start_time))

        # Sync Live Job
        live_interval = s_dict.get('batch_live_interval', 5)
        live_enabled = s_dict.get('batch_live_enabled', 'true') == 'true'
        live_start_time = s_dict.get('batch_live_start_time', '19:00')
        
        job_live = scheduler.get_job('batch_live')
        if job_live:
            scheduler.reschedule_job('batch_live', trigger='interval', minutes=int(live_interval), start_date=get_next_run_time(live_start_time))
            if live_enabled: scheduler.resume_job('batch_live')
            else: scheduler.pause_job('batch_live')
        else:
            scheduler.add_job(task_live_score_updater, 'interval', minutes=int(live_interval), id='batch_live', start_date=get_next_run_time(live_start_time))
        
        print("Scheduler settings synchronized with DB.")
    except Exception as e:
        print(f"Error syncing scheduler: {e}")
    finally:
        db.close()

def start_scheduler():
    init_settings()
    
    # Initialize jobs using sync logic
    sync_scheduler_settings()
    
    scheduler.start()
    print("Scheduler started and synchronized.")

