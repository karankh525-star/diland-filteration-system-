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
