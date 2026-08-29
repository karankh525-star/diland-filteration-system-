import streamlit as st
import pandas as pd
import re
import asyncio
import requests
from datetime import datetime, timezone
import io
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# --- API CREDENTIALS ---
API_ID = 32862363
API_HASH = "73ac9de4fbf7087e99a6ce9b0d46e25f"
AGIFY_KEY = "e6d7d4a5debe860b1078275454db5c8b"
GENDERIZE_KEY = "0f1bef8f172675dbb5c5be9f1ba1e2cc"

# --- LANGUAGE TRANSLATIONS ---
LANG = {
    "EN": {
        "title": "Telegram Data Enrichment",
        "sidebar_title": "Settings",
        "upload_label": "Upload .txt file with phone numbers",
        "process_btn": "Start Processing",
        "download_btn": "Download Excel (.xlsx)",
        "status_processing": "Processing numbers... Please wait.",
        "status_done": "Processing Complete!",
        "error_file": "Please upload a valid .txt file.",
        "col_phone": "Phone", "col_uid": "UID", "col_username": "Username",
        "col_lastseen": "Last Seen", "col_activedays": "Active Days",
        "col_age": "Age", "col_gender": "Gender", "col_race": "Origin/Race"
    },
    "ZH": {
        "title": "Telegram 数据丰富化",
        "sidebar_title": "设置",
        "upload_label": "上传包含电话号码的 .txt 文件",
        "process_btn": "开始处理",
        "download_btn": "下载 Excel (.xlsx)",
        "status_processing": "正在处理号码... 请稍候。",
        "status_done": "处理完成！",
        "error_file": "请上传有效的 .txt 文件。",
        "col_phone": "电话", "col_uid": "用户ID", "col_username": "用户名",
        "col_lastseen": "最后在线", "col_activedays": "活跃天数",
        "col_age": "年龄", "col_gender": "性别", "col_race": "来源/种族"
    }
}

# --- HELPER FUNCTIONS ---
def extract_phone_numbers(text):
    """Extracts and cleans international phone numbers from text."""
    raw_numbers = text.split('\n')
    cleaned = []
    for num in raw_numbers:
        clean_num = re.sub(r'\D', '', num)
        if clean_num:
            cleaned.append("+" + clean_num)
    return list(set(cleaned))

def fetch_demographics(first_name):
    """Fetches Age, Gender, and Race from external APIs."""
    if not first_name:
        return "Unknown", "Unknown", "Unknown"
    
    age, gender, race = "Unknown", "Unknown", "Unknown"
    
    try:
        # Age
        res_age = requests.get(f"https://api.agify.io?name={first_name}&apikey={AGIFY_KEY}").json()
        age = res_age.get('age', 'Unknown')
        
        # Gender
        res_gen = requests.get(f"https://api.genderize.io?name={first_name}&apikey={GENDERIZE_KEY}").json()
        gender = res_gen.get('gender', 'Unknown')
        
        # Race/Nationality
        res_nat = requests.get(f"https://api.nationalize.io?name={first_name}").json()
        if res_nat.get('country') and len(res_nat['country']) > 0:
            race = res_nat['country'][0]['country_id']
            
    except Exception as e:
        pass
        
    return age, gender, race

async def process_telegram_data(phone_numbers, t):
    """Connects to Telegram via Telethon and processes numbers."""
    client = TelegramClient('session_name', API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        st.error("Telegram session not authorized. Please run locally first to authenticate via OTP.")
        return []

    results = []
    progress_bar = st.progress(0)
    
    for i, phone in enumerate(phone_numbers):
        try:
            user = await client.get_entity(phone)
            
            uid = user.id
            username = user.username if user.username else "None"
            first_name = user.first_name if user.first_name else ""
            
            # Calculate Last Seen & Active Days
            last_seen = "Hidden/Unknown"
            active_days = "Unknown"
            
            if hasattr(user.status, 'was_online'):
                last_online = user.status.was_online
                last_seen = last_online.strftime('%Y-%m-%d %H:%M:%S')
                now = datetime.now(timezone.utc)
                delta = now - last_online
                active_days = str(delta.days)
            
            # Fetch Demographics
            age, gender, race = fetch_demographics(first_name)
            
            results.append({
                t["col_phone"]: phone,
                t["col_uid"]: uid,
                t["col_username"]: username,
                t["col_lastseen"]: last_seen,
                t["col_activedays"]: active_days,
                t["col_age"]: age,
                t["col_gender"]: gender,
                t["col_race"]: race
            })
            
        except Exception as e:
            results.append({
                t["col_phone"]: phone,
                t["col_uid"]: "Not Found",
                t["col_username"]: "Not Found",
                t["col_lastseen"]: "-",
                t["col_activedays"]: "-",
                t["col_age"]: "-",
                t["col_gender"]: "-",
                t["col_race"]: "-"
            })
        
        # Rate Limiting
        await asyncio.sleep(0.5)
        progress_bar.progress((i + 1) / len(phone_numbers))
        
    await client.disconnect()
    return results

# --- STREAMLIT UI ---
st.set_page_config(page_title="Data Enrichment App", layout="wide")

# Sidebar
language = st.sidebar.radio("Language / 语言", ["English (EN)", "中文 (ZH)"])
lang_code = "EN" if "EN" in language else "ZH"
t = LANG[lang_code]

st.sidebar.header(t["sidebar_title"])
st.sidebar.info("API Keys Configured Internally.")

st.title(t["title"])

# File Upload (TXT only)
uploaded_file = st.file_uploader(t["upload_label"], type=["txt"])

if uploaded_file is not None:
    content = uploaded_file.getvalue().decode("utf-8")
    phone_numbers = extract_phone_numbers(content)
    
    st.write(f"Loaded {len(phone_numbers)} numbers.")
    
    if st.button(t["process_btn"]):
        with st.spinner(t["status_processing"]):
            # Create a new event loop for async Telethon operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            final_data = loop.run_until_complete(process_telegram_data(phone_numbers, t))
            loop.close()
            
            if final_data:
                df = pd.DataFrame(final_data)
                st.success(t["status_done"])
                st.dataframe(df)
                
                # Export to XLSX
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                excel_data = output.getvalue()
                
                st.download_button(
                    label=t["download_btn"],
                    data=excel_data,
                    file_name="enriched_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
