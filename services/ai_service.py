from datetime import datetime
import os
import time
from google import genai
from google.genai import types
import json
from typing import Dict, Any, List, Union
from bs4 import BeautifulSoup, Comment

# To be set via environment mapping
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "[ENCRYPTION_KEY]")

# Initialize GenAI Client
client = genai.Client(api_key=GEMINI_API_KEY)

default_generation_config = types.GenerateContentConfig(
    temperature=0.2,
    top_p=1.0,
    max_output_tokens=65536,
    response_mime_type="application/json",
    thinking_config=types.ThinkingConfig(
        thinking_budget=0,
    ),
    safety_settings=[
        types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
        types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
        types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
        types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
    ]
)

MODEL_PRO = "gemini-3.1-pro-preview"
MODEL_FLASH = "gemini-3-flash-preview"

def prompt_gemini_json(contents: Union[str, List[Any]]) -> Any:
    # Try Pro first
    last_text = ""
    try:
        response = client.models.generate_content(
            model=MODEL_PRO,
            contents=contents,
            config=default_generation_config
        )
        print("Finish reason:", response.candidates[0].finish_reason)
        print("Usage:", response.usage_metadata)
        print("Thoughts tokens:", getattr(response.usage_metadata, "thoughts_token_count", 0))
        print("Output tokens:", response.usage_metadata.candidates_token_count)
        last_text = response.text
        with open(f"./wiki/debug_ai_pro_{datetime.now().year}.json", "w", encoding="utf-8") as f:
            f.write(last_text)
            
        text = last_text.replace('```json', '').replace('```', '')
        return json.loads(text)
    except Exception as e_pro:
        print(f"DEBUG: Gemini Pro Failed: {e_pro}. Falling back to Flash...")
        # Fallback to Flash
        try:
            response = client.models.generate_content(
                model=MODEL_FLASH,
                contents=contents,
                config=default_generation_config
            )
            print("Finish reason:", response.candidates[0].finish_reason)
            print("Usage:", response.usage_metadata)
            print("Thoughts tokens:", getattr(response.usage_metadata, "thoughts_token_count", 0))
            print("Output tokens:", response.usage_metadata.candidates_token_count)
            last_text = response.text
            with open(f"./wiki/debug_ai_flash_{datetime.now().year}.json", "w", encoding="utf-8") as f:
                f.write(last_text)
                
            text = last_text.replace('```json', '').replace('```', '')
            return json.loads(text)
        except Exception as e_flash:
            print(f"DEBUG: Gemini Flash also Failed: {e_flash}")
            return None


def generate_match_odds_and_analysis(team1: str, team2: str, stage: str = "", stadium: str = "", start_time: str = "") -> Dict:
    prompt = f"""
    You are an expert football betting analyst. 
    Analyze the upcoming match logically between Đội 1: "{team1}" and Đội 2: "{team2}".
    Vòng đấu: {stage}, Sân vận động: {stadium}, Thời gian: {start_time}.

    Requirements:
    1. If team names are "Không xác định" (Unknown), please use the provided context (time/stage/stadium) to infer which teams are likely playing (e.g., Winner Group A vs Runner-up Group B) and state it in the analysis.
    2. Determine the Asian Handicap as a multiple of 0.5 (e.g., 0, 0.5, 1.0, 1.5, 2.0).
    3. Return ONLY a valid JSON object with keys:
       - "handicap" (number)
       - "favorite_team" (string: match one of the input names or the inferred predicted team name)
       - "underdog_team" (string)
       - "analysis_text" (string: short 2-3 sentences in Vietnamese. Start with "Dự đoán tỷ số: X - Y. ")
       - "predicted_team1" (string, ONLY if team1 was "Không xác định", predict the real team name)
       - "predicted_team2" (string, ONLY if team2 was "Không xác định", predict the real team name)
       - "predicted_stadium" (string, ONLY if stadium was "Không xác định", predict the real stadium name)
    """
    res = prompt_gemini_json(prompt)
    if res and "handicap" in res:
        import math
        res["handicap"] = math.ceil(res["handicap"] * 2) / 2
        return res
        
    return {
        "handicap": 0.5,
        "favorite_team": team1,
        "underdog_team": team2,
        "analysis_text": "Chưa có phân tích cho trận đấu này."
    }

def simulate_match_live_update(home_team: str, away_team: str, current_home_score: int, current_away_score: int) -> Dict:
    prompt = f"""
    Simulate a football match event between {home_team} and {away_team}.
    Current score: {home_team} {current_home_score} - {current_away_score} {away_team}.
    Decide if a goal is scored in the next 5 minutes.
    Return ONLY a valid JSON object with keys:
    - "home_score" (integer, new score)
    - "away_score" (integer, new score)
    - "match_finished" (boolean, probabilistically true if you think 90 minutes are up, let's say 10% chance for simulation purposes)
    """
    return prompt_gemini_json(prompt) or {
        "home_score": current_home_score,
        "away_score": current_away_score,
        "match_finished": False
    }

def sanitize_html_content(content: str) -> str:
    """
    Xóa bỏ các thẻ và thuộc tính thừa thãi để tối ưu token khi gửi cho AI.
    """
    soup = BeautifulSoup(content, 'html.parser')
    
    # Xóa các thẻ nội dung không cần thiết
    for tag in soup(["input", "footer", "header", "nav", "p", "script", "style", "meta", "link", "img", "button", "picture", "video", "audio", "iframe", "noscript", "ul", "li"]):
        tag.decompose()
        
    # Xóa comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        
    # Xóa các thuộc tính CSS hoặc Navigation không cần thiết cho việc lấy dữ liệu trận đấu
    unwanted_attrs = ["align", "rowspan", "width", "scope", "hidden", "itemprop", "title", "typeof", "data-mw", "data-mw-section-id", "aria-labelledby", "role", "tabindex", "colspan", "itemtype", "itemscope", "about", "class", "rel", "href", "style", "target", "onclick", "id", "data-native-id", "src"]
    for tag in soup.find_all():
        for attr in unwanted_attrs:
            if tag.has_attr(attr):
                del tag[attr]

    # Mở (unwrap) các thẻ span và a để giữ lại nội dung nhưng giảm bớt markup
    for tag in soup(["span", "a"]):
        tag.unwrap()

    # Xóa các tag trống hoặc chỉ có khoảng trắng (recursive)
    for tag in reversed(soup.find_all()):
        if not tag.get_text(strip=True) and not tag.find():
            tag.decompose()
                
    return str(soup)

def extract_matches_from_file(file_path: str, year: int) -> Dict[str, Any]:
    """
    Sử dụng Google File API để upload file data và parse bằng Gemini.
    """
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return None

    upload_path = file_path
    temp_sanitized = None
    is_html = file_path.lower().endswith(('.html', '.htm'))
    
    if is_html:
        print(f"Sanitizing HTML file: {file_path}...")
        try:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            
            sanitized_content = sanitize_html_content(content)
            temp_sanitized = f"{file_path}.sanitized.html"
            with open(temp_sanitized, "w", encoding="utf-8") as f:
                f.write(sanitized_content)
            upload_path = temp_sanitized
            print(f"Sanitization complete. File size reduced from {len(content)} to {len(sanitized_content)} characters.")
        except Exception as e:
            print(f"WARNING: Sanitization failed, using original file: {e}")

    # 1. Upload file
    print(f"Uploading file to Gemini: {upload_path}...")
    file_obj = client.files.upload(file=upload_path)
    
    # Wait for file to be processed
    while file_obj.state.name == "PROCESSING":
        time.sleep(2)
        file_obj = client.files.get(name=file_obj.name)
    
    if file_obj.state.name == "FAILED":
        print(f"ERROR: File upload failed for {file_path}")
        return None

    prompt = f"""
    You are an AI Data Extractor. I have uploaded a file containing World Cup {year} match information.
    Your task is to parse this content and extract ALL matches into the EXACT JSON format required.

    REQUIRED FORMAT:
    {{
        "total": 104,
        "note": "Giờ hiển thị là Giờ Việt Nam (ICT, UTC+7)",
        "rounds": {{ "Vòng bảng": 72, "Vòng 32": 16, "Vòng 16": 8, "Tứ kết": 4, "Bán kết": 2, "Hạng 3": 1, "Chung kết": 1 }},
        "matches": [
            {{
                "match": 1,
                "round": "Vòng bảng",
                "round_order": 1,
                "team1": {{ "code": "us", "name": "Hoa kỳ" }},
                "team2": {{ "code": "jp", "name": "Nhật Bản" }},
                "datetime": "12/06/2026 08:00",
                "venue": {{ "stadium": "XXXX", "city": "XXXXX", "country": "XXXXX" }}
            }},
            ...
        ]
    }}

    Rules:
    1. EXTRACT as many matches as you can find. Try to reach 104 if the data is complete.
    2. If a team code is missing, try to infer it (e.g., "Germany" -> "de").
    3. Ensure dates are in "DD/MM/YYYY HH:MM" format. Convert to ICT (UTC+7) if the source has a different timezone.
    4. If the data describes a knockout match like "Winner Group A vs Runner-up Group B", use those as names.
    5. round_order: "Vòng bảng": 1, "Vòng 32": 2, "Vòng 16": 3, "Tứ kết": 4, "Bán kết": 5, "Hạng 3": 6, "Chung kết": 7
    6. Return ONLY valid JSON.
    """
    
    try:
        res = prompt_gemini_json([prompt, file_obj])
        return res
    finally:
        # Cleanup file from Gemini storage
        try:
            print(f"Cleaning up file from Gemini: {file_obj.name}")
            client.files.delete(name=file_obj.name)
        except Exception as e:
            print(f"WARNING: Cleanup failed for {file_obj.name}: {e}")
            
        # Cleanup local sanitized temp file
        if temp_sanitized and os.path.exists(temp_sanitized):
            try:
                print(f"Removing local sanitized file: {temp_sanitized}")
                os.remove(temp_sanitized)
            except Exception as e:
                print(f"WARNING: Failed to remove local temp file {temp_sanitized}: {e}")
