import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db, models, schemas
from services.auth import get_password_hash, verify_password, create_access_token, generate_otp, ACCESS_TOKEN_EXPIRE_MINUTES
from services.email_service import send_otp_email_async

router = APIRouter(prefix="/api/auth", tags=["auth"])

APP_URL = os.environ.get("APP_URL", "http://localhost:8080")

@router.post("/register", response_model=dict)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Auto-append domain if missing @
    if "@" not in user.email:
        user.email = user.email.strip() + "@runsystem.net"
    
    if not user.email.lower().endswith("@runsystem.net"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận email @runsystem.net")

    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = models.User(
        email=user.email, 
        full_name=user.full_name,
        password_hash=get_password_hash(user.password), 
        is_active=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate activation token (reusing OTP mechanism)
    otp_code = generate_otp()
    expires = datetime.utcnow() + timedelta(hours=24) # Links last longer than OTP
    
    db_otp = models.OTP(email=user.email, code=otp_code, expires_at=expires)
    db.add(db_otp)
    db.commit()
    
    # Send activation link via email
    activation_link = f"{APP_URL}/api/auth/activate?email={user.email}&token={otp_code}"
    send_otp_email_async(user.email, activation_link)
    
    return {"message": "Đăng ký thành công! Vui lòng kiểm tra email của bạn để kích hoạt tài khoản."}

@router.get("/activate")
def activate_account(email: str, token: str, db: Session = Depends(get_db)):
    otp_record = db.query(models.OTP).filter(
        models.OTP.email == email, 
        models.OTP.code == token
    ).first()
    
    if not otp_record or otp_record.expires_at < datetime.utcnow():
        # Redirect to index with error param
        return RedirectResponse(url=f"{APP_URL}/static/index.html?error=invalid_token")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        user.is_active = True
        db.delete(otp_record)
        db.commit()
        # Redirect to index with success param
        return RedirectResponse(url=f"{APP_URL}/static/index.html?activated=true")
    
    return RedirectResponse(url=f"{APP_URL}/static/index.html?error=user_not_found")

@router.post("/verify-otp", response_model=dict)
def verify_otp(data: schemas.OTPVerify, db: Session = Depends(get_db)):
    # Find OTP
    otp_record = db.query(models.OTP).filter(
        models.OTP.email == data.email, 
        models.OTP.code == data.code
    ).first()
    
    if not otp_record or otp_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Activate user
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if user:
        user.is_active = True
        db.delete(otp_record) # remove used OTP
        db.commit()
        return {"message": "Account activated successfully. You can now login."}
    
    raise HTTPException(status_code=404, detail="User not found")

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.strip()
    if "@" not in email:
        email += "@runsystem.net"
        
    user = db.query(models.User).filter(models.User.email == email).first()
    
    print(f"DEBUG LOGIN: Email={email}, Found User={'Yes' if user else 'No'}")
    
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    try:
        is_correct = verify_password(form_data.password, user.password_hash)
        print(f"DEBUG LOGIN: Password Correct={is_correct}, User Active={user.is_active}")
        
        if not is_correct:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        print(f"DEBUG LOGIN ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý mật khẩu trên Server: {str(e)}")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản chưa được kích hoạt. Vui lòng kiểm tra email.")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

from dependencies import get_current_active_user

@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    # Get active year
    year_setting = db.query(models.Setting).filter_by(key="active_wc_year").first()
    active_year = int(year_setting.value) if year_setting else 2026

    stats = db.query(models.UserStats).filter_by(user_id=current_user.id, year=active_year).first()
    
    # Initialize response with basic user info
    res = schemas.UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        total_correct=0,
        total_wrong=0,
        money_lost=0
    )
    
    if stats:
        res.total_correct = stats.total_correct
        res.total_wrong = stats.total_wrong
        res.money_lost = stats.money_lost
        
    return res

@router.post("/change-password")
def change_password(data: schemas.ChangePasswordRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác.")
    
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Đổi mật khẩu thành công!"}
