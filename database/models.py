from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy import UniqueConstraint

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String)
    is_active = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    predictions = relationship("Prediction", back_populates="user")
    stats = relationship("UserStats", back_populates="user")

class UserStats(Base):
    __tablename__ = "user_stats"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    year = Column(Integer, index=True)
    total_correct = Column(Integer, default=0)
    total_wrong = Column(Integer, default=0)
    money_lost = Column(Integer, default=0)
    
    __table_args__ = (UniqueConstraint('user_id', 'year', name='uq_user_year_stats'),)
    
    user = relationship("User", back_populates="stats")

class OTP(Base):
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    code = Column(String)
    expires_at = Column(DateTime)

class Country(Base):
    __tablename__ = "countries"
    code = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    name_vn = Column(String, index=True, nullable=True)
    flag_data = Column(String) # Base64 encoded image data

class Stadium(Base):
    __tablename__ = "stadiums"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True, index=True)
    value = Column(String)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, default=2026, index=True)
    match_no = Column(Integer, index=True)
    
    __table_args__ = (UniqueConstraint('year', 'match_no', name='uq_match_year_no'),)

    api_match_id = Column(String, unique=True, index=True)
    stage = Column(String) # e.g., Group Stage, Round of 16, Quarter-Final
    group_name = Column(String, nullable=True) # e.g. A, B, C...
    start_time = Column(DateTime)
    home_team = Column(String)
    home_team_code = Column(String, nullable=True)
    away_team = Column(String)
    away_team_code = Column(String, nullable=True)
    stadium = Column(String, default="TBD")
    home_score = Column(Integer, default=None, nullable=True)
    away_score = Column(Integer, default=None, nullable=True)
    status = Column(String, default="SCHEDULED") # SCHEDULED, READY, LIVE, FINISHED
    locked = Column(Boolean, default=False)
    lucky_star_enabled = Column(Boolean, default=False)

    odds = relationship("MatchOdds", back_populates="match", uselist=False)
    predictions = relationship("Prediction", back_populates="match")

class MatchOdds(Base):
    __tablename__ = "match_odds"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    handicap = Column(Float) # e.g. 1.5
    favorite_team = Column(String) # the team that gives the handicap
    underdog_team = Column(String)
    analysis_text = Column(String)
    
    match = relationship("Match", back_populates="odds")

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    match_id = Column(Integer, ForeignKey("matches.id"))
    chosen_team = Column(String)
    use_lucky_star = Column(Boolean, default=False)
    result = Column(String, default=None, nullable=True) # WON, LOST, DRAW
    money_changed = Column(Integer, default=0)

    user = relationship("User", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")
