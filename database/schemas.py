from pydantic import BaseModel, EmailStr
from typing import Optional
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

class StadiumResponse(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes = True

class StadiumUpdate(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None

class SettingUpdate(BaseModel):
    penalty_per_loss: Optional[int] = None
    lucky_star_amount: Optional[int] = None
    default_prediction_time: Optional[str] = None
    
    batch_predict_interval: Optional[int] = None
    batch_predict_enabled: Optional[bool] = None
    batch_predict_start_time: Optional[str] = None
    batch_live_interval: Optional[int] = None
    batch_live_enabled: Optional[bool] = None
    batch_live_start_time: Optional[str] = None
    active_wc_year: Optional[int] = None

class CountryUpdate(BaseModel):
    name_vn: str

class UserAdminUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class MatchOddsReponse(BaseModel):
    handicap: float
    favorite_team: str
    underdog_team: str
    analysis_text: str

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
    home_score: Optional[int]
    away_score: Optional[int]
    status: str
    locked: bool
    lucky_star_enabled: bool
    home_team_vn: Optional[str] = None
    away_team_vn: Optional[str] = None
    odds: Optional[MatchOddsReponse]

    class Config:
        from_attributes = True

class PredictionCreate(BaseModel):
    match_id: int
    chosen_team: str
    use_lucky_star: bool = False

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
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
