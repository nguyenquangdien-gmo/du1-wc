from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str

class OTPVerify(BaseModel):
    email: str
    code: str

class Token(BaseModel):
    access_token: str
    token_type: str

class YearCreate(BaseModel):
    year: int

class CountryResponse(BaseModel):
    code: str
    name: str
    name_vn: Optional[str] = None
    flag_data: Optional[str] = None

    class Config:
        from_attributes = True

class StadiumResponse(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes = True

class MatchOddsReponse(BaseModel):
    handicap: float
    favorite_team: str
    underdog_team: str
    analysis_text: str

    class Config:
        from_attributes = True

class PredictionResponse(BaseModel):
    id: int
    user_id: int
    match_id: int
    chosen_team: str
    use_lucky_star: bool
    result: Optional[str]
    money_changed: int

    class Config:
        from_attributes = True

class MatchResponse(BaseModel):
    id: int
    year: int
    match_no: int
    api_match_id: str
    stage: str
    group_name: Optional[str] = None
    start_time: datetime
    home_team: str
    home_team_code: Optional[str] = None
    home_team_flag: Optional[str] = None
    away_team: str
    away_team_code: Optional[str] = None
    away_team_flag: Optional[str] = None
    stadium: str
    stadium_country: Optional[str] = None
    home_score: Optional[int]
    away_score: Optional[int]
    status: str
    locked: bool
    lucky_star_enabled: bool
    home_team_vn: Optional[str] = None
    away_team_vn: Optional[str] = None
    odds: Optional[MatchOddsReponse]
    
    notified_30m: Optional[bool] = False
    notified_5m: Optional[bool] = False
    notified_0m: Optional[bool] = False
    comment_count: int = 0
    user_prediction: Optional[PredictionResponse] = None # Added for UX

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    total_correct: int = 0
    total_wrong: int = 0
    money_lost: int = 0
    name_vn: Optional[str] = None # Added for country display in match list if nested

    class Config:
        from_attributes = True

class StadiumUpdate(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None

class SettingUpdate(BaseModel):
    penalty_per_loss: Optional[int] = None
    lucky_star_amount: Optional[int] = None
    tournament_champion_fee: Optional[int] = None
    tournament_player_fee: Optional[int] = None
    
    batch_predict_interval: Optional[int] = None
    batch_predict_enabled: Optional[bool] = None
    batch_live_interval: Optional[int] = None
    batch_live_enabled: Optional[bool] = None
    active_wc_year: Optional[int] = None
    
    # ChatOps Notification Settings
    mattermost_enabled: Optional[bool] = None
    mattermost_url: Optional[str] = None
    mattermost_bot_token: Optional[str] = None
    mattermost_channel_id: Optional[str] = None
    mattermost_root_id: Optional[str] = None
    mattermost_message_template: Optional[str] = None

class CountryUpdate(BaseModel):
    name_vn: str

class UserAdminUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class PredictionCreate(BaseModel):
    match_id: int
    chosen_team: str
    use_lucky_star: bool = False

class AdminMatchUpdate(BaseModel):
    home_team: Optional[str] = None
    home_team_code: Optional[str] = None
    away_team: Optional[str] = None
    away_team_code: Optional[str] = None
    stadium: Optional[str] = None
    group_name: Optional[str] = None
    start_time: Optional[datetime] = None
    status: Optional[str] = None  # SCHEDULED, READY, LIVE, FINISHED
    locked: Optional[bool] = None
    lucky_star_enabled: Optional[bool] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    
    odds_favorite_team: Optional[str] = None
    odds_underdog_team: Optional[str] = None
    odds_handicap: Optional[float] = None
    odds_analysis_text: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ProfileUpdate(BaseModel):
    full_name: str

class CommentCreate(BaseModel):
    content: str

class CommentUpdate(BaseModel):
    content: str

class CommentReactionStats(BaseModel):
    reaction_type: str
    count: int
    user_reacted: bool = False

class CommentResponse(BaseModel):
    id: int
    match_id: int
    user_id: int
    user_full_name: Optional[str]
    user_email_prefix: str
    content: str
    created_at: datetime
    reactions: List[CommentReactionStats] = []

    class Config:
        from_attributes = True

class ReactionToggle(BaseModel):
    reaction_type: str # 👍, ❤️, 😂, 😮, 😢

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

class TournamentVoteCreate(BaseModel):
    category: str # CHAMPION, BEST_PLAYER
    selection: str

class TournamentVoteResponse(BaseModel):
    id: int
    user_id: int
    user_full_name: Optional[str]
    category: str
    selection: str
    fee_paid: int
    
    class Config:
        from_attributes = True

class TournamentStatus(BaseModel):
    year: int
    champion_locked: bool
    player_locked: bool
    is_finalized: bool
    champion_pool: int
    player_pool: int
    champion_fee: int
    player_fee: int
    user_votes: List[TournamentVoteResponse]
    all_votes: List[TournamentVoteResponse]

class TournamentResultUpdate(BaseModel):
    champion_result: Optional[str] = None
    player_result: Optional[str] = None
    champion_locked: Optional[bool] = None
    player_locked: Optional[bool] = None

class TournamentPlayerCandidateCreate(BaseModel):
    name: str
    country_code: Optional[str] = None
    year: int

class TournamentPlayerCandidateResponse(BaseModel):
    id: int
    name: str
    country_code: Optional[str] = None
    year: int

    class Config:
        from_attributes = True
