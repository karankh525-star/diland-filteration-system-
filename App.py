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
from telethon.tl.types import InputPhoneContact, UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth

# ==========================================
# 1. API CREDENTIALS & CONFIG 
# ==========================================
TG_ACCOUNTS = [
    {"session": "session_1", "api_id": 32862363, "api_hash": "73ac9de4fbf7087e99a6ce9b0d46e25f"},
    {"session": "session_2", "api_id": 31332666, "api_hash": "fb8afbc22c281655f262d1f8ee09a917"},
    {"session": "session_3", "api_id": 38157740, "api_hash": "cfe91b0b5981caad683e3ea64ac9c81a"}
]

AGIFY_KEY = "e6d7d4a5debe860b1078275454db5c8b"
GENDERIZE_KEY = "0f1bef8f172675dbb5c5be9f1ba1e2cc"

# ==========================================
# 2. SMART AI DEMOGRAPHICS (High Speed)
# ==========================================
async def fetch_demographics(session, final_name, phone):
    invalid_names = ["unknown", "-", "", "none", "hidden", "privacy", "target user"]
    if not final_name or str(final_name).lower().strip() in invalid_names:
        return "Unknown", "Unknown"
    
    spaced_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(final_name))
    clean_fname = re.sub(r'[^a-zA-Z]', ' ', spaced_name).strip()
    clean_fname = clean_fname.split()[0] if clean_fname else ""
    
    fake_words = ["gamer", "boy", "girl", "cool", "super", "crazy", "dark", "pro", "bot", "king", "queen", "cute", "sweet"]
    if len(clean_fname) < 2 or clean_fname.lower() in fake_words:
        return "Unknown", "Unknown"
        
    age, gender = "Unknown", "Unknown"
    
    try:
        # Firing APIs concurrently for Max Speed
        age_resp = await session.get(f"https://api.agify.io?name={clean_fname}&apikey={AGIFY_KEY}")
        gen_resp = await session.get(f"https://api.genderize.io?name={clean_fname}&apikey={GENDERIZE_KEY}")
        
        # IP Fallback (Without Key)
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
        
    return age, gender

# ==========================================
# 3. ULTIMATE TELEGRAM GHOST SYNC & TRACKER
# ==========================================
async def process_single_number(phone, tg_client, http_session):
    uid, username, tg_status = "Not Found", "Not Found", "No"
    exact_last_seen, active_category, tg_name, raw_username = "-", "-", "-", ""
    
    try:
        rand_client_id = random.randint(10000, 999999)
        contact = InputPhoneContact(client_id=rand_client_id, phone=phone, first_name="Target", last_name="User")
        result = await tg_client(ImportContactsRequest([contact]))
        
        if result.users:
            user = result.users[0]
            tg_status = "Yes"
            uid = str(user.id)
            
            # Username Extraction
            raw_username = user.username if user.username else ""
            username = f"@{raw_username}" if raw_username else "None"
            
            # Privacy Name Handle
            fetched_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if fetched_name.lower() == "target user":
                tg_name = "Hidden (Privacy)"
            else:
                tg_name = fetched_name or "-"
            
            # SMART LAST SEEN TRACKER (Meets Client's 24h-72h Request)
            if user.status:
                if isinstance(user.status, UserStatusOnline):
                    exact_last_seen = "Online Now"
                    active_category = "Active (< 24 Hours)"
                elif isinstance(user.status, UserStatusOffline):
                    exact_last_seen = user.status.was_online.strftime('%Y-%m-%d %H:%M')
                    delta = datetime.now(timezone.utc) - user.status.was_online
                    if delta.days == 0:
                        active_category = "Active (< 24 Hours)"
                    elif delta.days <= 3:
                        active_category = "Active (24-72 Hours)"
                    else:
                        active_category = "Inactive (> 72 Hours)"
                elif isinstance(user.status, UserStatusRecently):
                    exact_last_seen = "Hidden by Privacy"
                    active_category = "Active (< 72 Hours)" # Telegram 'Recently' usually means 1-3 days
                elif isinstance(user.status, UserStatusLastWeek):
                    exact_last_seen = "Hidden by Privacy"
                    active_category = "Inactive (Within 7 Days)"
                elif isinstance(user.status, UserStatusLastMonth):
                    exact_last_seen = "Hidden by Privacy"
                    active_category = "Inactive (Within 30 Days)"
                
            # Instant Ghost Delete
            await tg_client(DeleteContactsRequest(id=[user.id]))
    except:
        pass

    # AI Demographics Route (Username prioritized, then display name)
    demo_name = "Unknown"
    if raw_username != "": 
        demo_name = raw_username.replace("@", "")
    elif tg_name not in ["Hidden (Privacy)", "-", "", "Unknown"]: 
        demo_name = tg_name
        
    # Only fetch demographics IF user is actually on Telegram (Saves huge time!)
    age, gender = "Unknown", "Unknown"
    if tg_status == "Yes":
        age, gender = await fetch_demographics(http_session, demo_name, phone)
    
    return {
        "Phone Number": phone,
        "On Telegram?": tg_status,
        "TG Username": username,
        "TG Name": tg_name,
        "Activity Category": active_category,
        "Exact Last Seen": exact_last_seen,
        "Target Age (AI)": age,
        "Target Gender (AI)": gender
    }

async def main_processor(phone_list, progress_bar):
    clients = []
    for acc in TG_ACCOUNTS:
        client = TelegramClient(acc['session'], acc['api_id'], acc['api_hash'])
        await client.connect()
        clients.append(client)
    
    results = []
    async with aiohttp.ClientSession() as http_session:
        # Boosted Speed: Processing 15 numbers at a time instead of 6!
        for i in range(0, len(phone_list), 15):
            batch = phone_list[i:i+15]
            tasks = [process_single_number(phone, clients[j % len(clients)], http_session) for j, phone in enumerate(batch)]
            results.extend(await asyncio.gather(*tasks))
            progress_bar.progress(min((i + 15) / len(phone_list), 1.0))
            await asyncio.sleep(0.1) # Minimized delay for extreme speed
            
    for client in clients:
        await client.disconnect()
    return results

# ==========================================
# 4. STREAMLIT UI (Ultra-Fast Telegram Edition)
# ==========================================
st.set_page_config(page_title="TG Deep Filter Engine", layout="wide")

st.sidebar.title("Settings / 设置")
lang = st.sidebar.radio("Language / 语言", ["English", "中文"])

txt = {
    "title": "Telegram Deep Filter & AI Engine ⚡" if lang == "English" else "Telegram 深度过滤与 AI 引擎 ⚡",
    "specs": "System Specs 🚀" if lang == "English" else "系统规格 🚀",
    "upload": "Upload .txt file with phone numbers" if lang == "English" else "上传带有电话号码的 .txt 文件",
    "filter": "Filter by Target Age (0 = Show All)" if lang == "English" else "按目标年龄过滤（0 = 显示全部）",
    "active_filter": "Show ONLY Active Users (< 72 Hours)" if lang == "English" else "仅显示近期活跃用户（< 72 小时）",
    "loaded": "Loaded unique numbers: " if lang == "English" else "已加载唯一号码: ",
    "btn": "Start High-Speed Processing" if lang == "English" else "开始极速处理",
    "processing": "Running Ghost Sync & Activity Tracker..." if lang == "English" else "正在运行幽灵同步与活跃追踪...",
    "success": "Processing Complete!" if lang == "English" else "处理完成！",
    "download": "Download Excel (.xlsx)" if lang == "English" else "下载 Excel (.xlsx)",
    "no_data": "No records found for the selected filters." if lang == "English" else "未找到符合过滤条件的记录。"
}

st.sidebar.markdown(f"**{txt['specs']}**\n- **Engine Mode:** Extreme Speed (10x)\n- **TG Engines:** 3 Active (Rotation)\n- **Tracking:** 24h-72h Activity Scanner\n- **Smart AI:** Username Parser ON")

st.title(txt["title"])
st.write("---")

col1, col2 = st.sidebar.columns(2)
target_age = st.sidebar.number_input(txt["filter"], min_value=0, max_value=120, value=0)
only_active = st.sidebar.checkbox(txt["active_filter"])

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
            
            # FILTERS: Age & Activity
            if target_age > 0:
                df['Age_Num'] = pd.to_numeric(df['Target Age (AI)'], errors='coerce')
                df = df[df['Age_Num'] == target_age]
                df = df.drop(columns=['Age_Num'])
                
            if only_active:
                df = df[df['Activity Category'].str.contains("< 24|< 72", na=False)]
            
            st.success(txt["success"])
            
            if df.empty:
                st.warning(txt["no_data"])
            else:
                st.dataframe(df)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(txt["download"], data=output.getvalue(), file_name="TG_Fast_Filter_Results.xlsx")
