import streamlit as st
import pandas as pd
import re
import asyncio
import aiohttp
import io
from datetime import datetime, timezone
from telethon import TelegramClient

# ==========================================
# 1. API CREDENTIALS
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
# 2. ASYNC FETCH FUNCTIONS
# ==========================================
async def check_whatsapp(session, phone):
    clean_num = phone.replace('+', '')
    url = f"https://7107.api.greenapi.com/waInstance{WS_INSTANCE_ID}/checkWhatsapp/{WS_API_TOKEN}"
    payload = {"phoneNumber": int(clean_num)}
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return "Yes" if data.get('existsWhatsapp') else "No"
            return "No"
    except:
        return "No"

async def fetch_demographics(session, first_name, phone):
    if not first_name or first_name == "-" or first_name.lower() == "unknown":
        age, gender = "Unknown", "Unknown"
    else:
        # Clean name to remove special/Chinese characters for Agify/Genderize lookup
        clean_fname = re.sub(r'[^\w\s]', '', first_name).strip()
        if not clean_fname:
            clean_fname = first_name.split()[0]
        else:
            clean_fname = clean_fname.split()[0]
            
        try:
            age_url = f"https://api.agify.io?name={clean_fname}&apikey={AGIFY_KEY}"
            gen_url = f"https://api.genderize.io?name={clean_fname}&apikey={GENDERIZE_KEY}"
            age_req, gen_req = await asyncio.gather(session.get(age_url), session.get(gen_url))
            age_data, gen_data = await age_req.json(), await gen_req.json()
            age = age_data.get('age', 'Unknown')
            gender = gen_data.get('gender', 'Unknown')
        except:
            age, gender = "Unknown", "Unknown"
            
    # Strict Region Lock for Indian Numbers
    if phone.startswith('+91') or phone.startswith('91'):
        race = "India"
    else:
        race = "International"
        
    return age, gender, race

async def process_single_number(phone, tg_client, http_session):
    ws_task = asyncio.create_task(check_whatsapp(http_session, phone))
    
    uid, username, tg_status, tg_last_seen, active_days, tg_name = "Not Found", "Not Found", "Invalid", "-", "-", "-"
    
    try:
        user = await tg_client.get_entity(phone)
        tg_status = "Active"
        uid = str(user.id)
        username = f"@{user.username}" if user.username else "None"
        tg_name = user.first_name if user.first_name else "-"
        
        if hasattr(user.status, 'was_online') and user.status.was_online:
            last_online = user.status.was_online
            tg_last_seen = last_online.strftime('%Y-%m-%d')
            active_days = str((datetime.now(timezone.utc) - last_online).days)
    except:
        pass

    ws_status = await ws_task
    age, gender, race = await fetch_demographics(http_session, tg_name, phone)
    
    return {
        "Phone Number": phone,
        "Telegram Name": tg_name,
        "Telegram (Active/Invalid)": tg_status,
        "TG UID": uid,
        "TG Username": username,
        "TG Last Seen": tg_last_seen,
        "TG Active Days": active_days,
        "WhatsApp (Yes/No)": ws_status,
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
        for i in range(0, len(phone_list), 3):
            batch = phone_list[i:i+3]
            tasks = []
            for j, phone in enumerate(batch):
                active_client = clients[j % len(clients)]
                tasks.append(process_single_number(phone, active_client, http_session))
            
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            progress_bar.progress(min((i + 3) / len(phone_list), 1.0))
            await asyncio.sleep(0.3)
            
    for client in clients:
        await client.disconnect()
    return results

# ==========================================
# 3. STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Pro Data Enrichment", layout="wide")

st.sidebar.title("Settings / 设置")
lang = st.sidebar.radio("Language / 语言", ["English", "中文"])

txt = {
    "title": "Telegram & WhatsApp OSINT Engine" if lang == "English" else "电报与WhatsApp数据丰富引擎",
    "upload": "Upload .txt file with phone numbers" if lang == "English" else "上传带有电话号码的 .txt 文件",
    "filter": "Filter by Target Age (0 = Show All)" if lang == "English" else "按目标年龄过滤（0 = 显示全部）",
    "loaded": "Loaded unique numbers: " if lang == "English" else "已加载唯一号码: ",
    "btn": "Start Processing" if lang == "English" else "开始处理",
    "processing": "Processing with 3 Engines in Parallel..." if lang == "English" else "正在使用3个引擎并行处理...",
    "success": "Processing Complete!" if lang == "English" else "处理完成！",
    "download": "Download Excel (.xlsx)" if lang == "English" else "下载 Excel (.xlsx)"
}

st.title(txt["title"])
st.sidebar.write("---")
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
            st.dataframe(df)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(txt["download"], data=output.getvalue(), file_name="Advanced_OSINT_Results.xlsx")
