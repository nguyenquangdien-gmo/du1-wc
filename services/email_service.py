import os
import threading
import urllib.request
import json
from datetime import datetime

def send_otp_email_async(receiver_email: str, otp: str):
    def send_email():
        # Lấy file cấu hình từ biến môi trường
        sender_email = os.environ.get("MAIL_USERNAME", "gmo_hcm@runsystem.vn")
        api_key = os.environ.get("MAIL_PASSWORD", "")
        
        if not api_key or sender_email == "your_email@gmail.com":
            # Fallback to console debug if email is not configured
            print(f"DEBUG (No Mail Config): Định gửi OTP cho {receiver_email} là {otp}")
            return
            
        url = "https://api.brevo.com/v3/smtp/email"
        
        current_year = datetime.now().year
        payload = {
            "sender": {
                "name": f"Hệ thống dự đoán WC{current_year}",
                "email": sender_email
            },
            "to": [
                {
                    "email": receiver_email
                }
            ],
            "subject": f'Kích hoạt tài khoản DU1-WC{current_year} của bạn',
            "htmlContent": f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #e94560;">Chào mừng bạn đến với DU1-WC{current_year}!</h2>
                    <p>Cảm ơn bạn đã đăng ký tham gia hệ thống dự đoán World Cup {current_year}.</p>
                    <p>Vui lòng nhấn vào nút bên dưới để kích hoạt tài khoản của bạn:</p>
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{otp}" style="background-color: #e94560; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">KÍCH HOẠT TÀI KHOẢN</a>
                    </p>
                    <p>Hoặc bạn cũng có thể copy và dán đường link sau vào trình duyệt:</p>
                    <p style="word-break: break-all; color: #666;">{otp}</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 0.8em; color: #888;">Nếu bạn không thực hiện đăng ký này, vui lòng bỏ qua email này.</p>
                </body>
            </html>
            """
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }, method='POST')

        try:
            with urllib.request.urlopen(req) as response:
                result = response.read().decode('utf-8')
                print(f"INFO: Hệ thống đã gọi API gửi email qua Brevo thành công tới {receiver_email}. Phản hồi: {result}")
        except Exception as e:
            print(f"ERROR: Lỗi gửi email qua Brevo API: {e}")
            
    # Chạy việc gửi email trong luồng riêng biệt để tránh làm chặn API response
    threading.Thread(target=send_email).start()

