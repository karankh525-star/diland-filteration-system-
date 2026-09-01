import streamlit as st
import pandas as pd
import re
import asyncio
import aiohttp
import io
import random
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from bs4 import BeautifulSoup
import urllib.parse

# ==========================================
# 1. API CREDENTIALS & CONFIG 
# ==========================================
TG_ACCOUNTS = [
    {"session": "session_1", "api_id": 32862363, "api_hash": "73ac9de4fbf7087e99a6ce9b0d46e25f"},
    {"session": "session_2", "api_id": 31332666, "api_hash": "fb8afbc22c281655f262d1f8ee09a917"},
    {"session": "session_3", "api_id": 38157740, "api_hash": "cfe91b0b5981caad683e3ea64ac9c81a"}
]

WS_INSTANCE_ID = "710722720740"
WS_API_TOKEN = "2105b56dc221492780d5a4cc427ec212eb50b4865ef948fd9d"

AGIFY_KEY = "e6d7d4a5debe860b1078275454db5c8b"
GENDERIZE_KEY = "0f1bef8f172675dbb5c5be9f1ba1e2cc"

# ==========================================
# 2. FREE OSINT & WHATSAPP ENGINES
# ==========================================
async def check_all_caller_ids(session, phone):
    """100% FREE DuckDuckGo OSINT Dorking - No API Key Required"""
    clean_num = phone.replace('+', '')
    
    if clean_num.startswith('1') and len(clean_num) == 11:
        search_term = f'"{clean_num[1:4]}-{clean_num[4:7]}-{clean_num[7:]}"'
    else:
        search_term = f'"{phone}"'

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_term)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with session.get(url, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                results = soup.find_all('a', class_='result__snippet')
                
                for res in results:
                    text = res.get_text().strip()
                    words = text.split()
                    for i in range(len(words)-1):
                        if words[i].istitle() and words[i+1].istitle() and len(words[i]) > 2:
                            return f"{words[i]} {words[i+1]}" 
    except:
        pass
    return "Unknown"

async def check_whatsapp_data(session, phone):
    clean_num = phone.replace('+', '')
    ws_status, ws_name = "No", "Unknown"
    
    try:
        async with session.post(f"https://7107.api.greenapi.com/waInstance{WS_INSTANCE_ID}/checkWhatsapp/{WS_API_TOKEN}", json={"phoneNumber": int(clean_num)}) as resp:
            if resp.status == 200:
                ws_status = "Yes" if (await resp.json()).get('existsWhatsapp') else "No"
                
        if ws_status == "Yes":
            async with session.post(f"https://7107.api.greenapi.com/waInstance{WS_INSTANCE_ID}/getContactInfo/{WS_API_TOKEN}", json={"chatId": f"{clean_num}@c.us"}) as resp:
                if resp.status == 200:
                    fetched_name = (await resp.json()).get('name', 'Unknown')
                    if fetched_name and str(fetched_name).strip() != "":
                        ws_name = str(fetched_name).strip()
    except:
        pass
    return ws_status, ws_name

async def fetch_demographics(session, final_name, phone):
    """SMART AI NAME SANITIZER FOR AGIFY (10x Accuracy)"""
    invalid_names = ["unknown", "-", "", "none", "hidden", "privacy", "target user", "target", "user", "admin", "null"]
    if not final_name or str(final_name).lower().strip() in invalid_names:
        return "Unknown", "Unknown", "India" if phone.startswith('+91') else "US/Intl"
    
    spaced_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(final_name))
    clean_fname = re.sub(r'[^a-zA-Z]', ' ', spaced_name).strip()
    clean_fname = clean_fname.split()[0] if clean_fname else ""
    
    fake_words = ["gamer", "boy", "girl", "cool", "super", "crazy", "dark", "pro", "bot", "king", "queen", "cute", "sweet"]
    if len(clean_fname) < 2 or clean_fname.lower() in fake_words:
        return "Unknown", "Unknown", "India" if phone.startswith('+91') else "US/Intl"
        
    age, gender = "Unknown", "Unknown"
    
    try:
        age_resp = await session.get(f"https://api.agify.io?name={clean_fname}&apikey={AGIFY_KEY}")
        gen_resp = await session.get(f"https://api.genderize.io?name={clean_fname}&apikey={GENDERIZE_KEY}")
        
        if age_resp.status in [429, 401]:
            age_resp = await session.get(f"https://api.agify.io?name={clean_fname}")
        if gen_resp.status in [429, 401]:
            gen_resp = await session.get(f"https://api.genderize.io?name={clean_fname}")

        if age_resp.status == 200:
            age_data = await age_resp.json()
            if age_data.get('age'): age = str(age_data['age'])
            
        if gen_resp.status == 200:
            gen_data = await gen_resp.json()
            if gen_data.get('gender'): gender = str(gen_data['gender'])
    except:
        pass
        
    return age, gender, "India" if phone.startswith('+91') else "US/Intl"

# ==========================================
# 3. TELEGRAM BYPASS & CORE PROCESSOR
# ==========================================
async def process_single_number(phone, tg_client, http_session):
    ws_task = asyncio.create_task(check_whatsapp_data(http_session, phone))
    caller_task = asyncio.create_task(check_all_caller_ids(http_session, phone))
    
    uid, username, tg_status, tg_last_seen, tg_name = "Not Found", "Not Found", "Not Available", "-", "-"
    
    try:
        rand_client_id = random.randint(10000, 999999)
        contact = InputPhoneContact(client_id=rand_client_id, phone=phone, first_name="Target", last_name="User")
        result = await tg_client(ImportContactsRequest([contact]))
        
        if result.users:
            user = result.users[0]
            tg_status = "Available"
            uid = str(user.id)
            
            raw_username = user.username if user.username else ""
            username = f"@{raw_username}" if raw_username else "None"
            
            fetched_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if fetched_name.lower() == "target user":
                tg_name = "Hidden (Privacy)"
            else:
                tg_name = fetched_name or "-"
            
            if hasattr(user.status, 'was_online') and user.status.was_online:
                last_online = user.status.was_online
                tg_last_seen = last_online.strftime('%Y-%m-%d')
                
            await tg_client(DeleteContactsRequest(id=[user.id]))
    except:
        pass

    ws_status, ws_name = await ws_task
    caller_name = await caller_task
    
    demo_name = "Unknown"
    if caller_name not in ["Unknown", "", "-"]: demo_name = caller_name
    elif ws_name not in ["Unknown", "", "-"]: demo_name = ws_name
    elif tg_name not in ["Hidden (Privacy)", "-", "", "Unknown"]: demo_name = tg_name
    elif raw_username != "": demo_name = raw_username.replace("@", "")
        
    age, gender, race = await fetch_demographics(http_session, demo_name, phone)
    
    return {
        "Phone Number": phone,
        "Real Name (OSINT)": caller_name,
        "WhatsApp Name": ws_name,
        "WhatsApp Status": ws_status,
        "Telegram Name": tg_name,
        "Telegram Username": username,
        "Telegram Status": tg_status,
        "TG Last Seen": tg_last_seen,
        "Target Age": age,
        "Target Gender": gender,
        "Race/Region": race
    }

async def main_processor(phone_list, progress_bar):
    clients = []
    for acc in TG_ACCOUNTS:
        client = TelegramClient(acc['session'], acc['api_id'], acc['api_hash'])
        await client.connect()
        clients.append(client)
    
    results = []
    async with aiohttp.ClientSession() as http_session:
        for i in range(0, len(phone_list), 6):
            batch = phone_list[i:i+6]
            tasks = [process_single_number(phone, clients[j % len(clients)], http_session) for j, phone in enumerate(batch)]
            results.extend(await asyncio.gather(*tasks))
            progress_bar.progress(min((i + 6) / len(phone_list), 1.0))
            await asyncio.sleep(0.3) 
            
    for client in clients:
        await client.disconnect()
    return results

# ==========================================
# 4. STREAMLIT UI 
# ==========================================
st.set_page_config(page_title="Ultimate OSINT Engine", layout="wide")

st.sidebar.title("Settings / 设置")
lang = st.sidebar.radio("Language / 语言", ["English", "中文"])

txt = {
    "title": "Ultimate OSINT Engine (Free-Tier)" if lang == "English" else "终极开源情报引擎 (免费版)",
    "specs": "System Specs 🚀" if lang == "English" else "系统规格 🚀",
    "upload": "Upload .txt file with phone numbers" if lang == "English" else "上传带有电话号码的 .txt 文件",
    "filter": "Filter by Target Age (0 = Show All)" if lang == "English" else "按目标年龄过滤（0 = 显示全部）",
    "loaded": "Loaded unique numbers: " if lang == "English" else "已加载唯一号码: ",
    "btn": "Start Processing" if lang == "English" else "开始处理",
    "processing": "Firing Parallel Engines... (AI Age Tracker ON)" if lang == "English" else "正在并行启动引擎... (开启AI年龄追踪)",
    "success": "Processing Complete!" if lang == "English" else "处理完成！",
    "download": "Download Excel (.xlsx)" if lang == "English" else "下载 Excel (.xlsx)",
    "no_data": "No records found for the selected age." if lang == "English" else "未找到符合所选年龄的记录。"
}

st.sidebar.markdown(f"**{txt['specs']}**\n- **TG Engines:** 3 Active (Rotation)\n- **WA Engines:** 1 Active (Green-API)\n- **OSINT:** Web Scraper (DuckDuckGo)\n- **Demo APIs:** 2 Active (Fallback ON)\n- **Smart AI:** Username Parser ON")

st.title(txt["title"])
st.write("---")

target_age = st.sidebar.number_input(txt["filter"], min_value=0, max_value=120, value=0)
uploaded_file = st.file_uploader(txt["upload"], type=["txt"])

if uploaded_file is not None:
    content = uploaded_file.getvalue().decode("utf-8")
    phone_numbers = list(set(["+" + re.sub(r'\D', '', num) for num in content.split('\n') if re.sub(r'\D', '', num)]))
    st.write(f'{txt["loaded"]} **{len(phone_numbers)}**')
    
    if st.button(txt["btn"]):
        with st.spinner(txt["processing"]):
            progress_bar = st.progress(0)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            final_data = loop.run_until_complete(main_processor(phone_numbers, progress_bar))
            loop.close()
            
            df = pd.DataFrame(final_data)
            
            if target_age > 0:
                df['Age_Num'] = pd.to_numeric(df['Target Age'], errors='coerce')
                df = df[df['Age_Num'] == target_age]
                df = df.drop(columns=['Age_Num'])
            
            st.success(txt["success"])
            
            if df.empty:
                st.warning(txt["no_data"])
            else:
                st.dataframe(df)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(txt["download"], data=output.getvalue(), file_name="Master_OSINT_Results.xlsx")
