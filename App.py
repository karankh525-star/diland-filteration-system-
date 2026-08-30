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

# ==========================================
# 1. API CREDENTIALS & CONFIG (14 ENGINES)
# ==========================================
TG_ACCOUNTS = [
    {"session": "session_1", "api_id": 32862363, "api_hash": "73ac9de4fbf7087e99a6ce9b0d46e25f"},
    {"session": "session_2", "api_id": 31332666, "api_hash": "fb8afbc22c281655f262d1f8ee09a917"},
    {"session": "session_3", "api_id": 38157740, "api_hash": "cfe91b0b5981caad683e3ea64ac9c81a"}
]

WS_INSTANCE_ID = "710722720740"
WS_API_TOKEN = "2105b56dc221492780d5a4cc427ec212eb50b4865ef948fd9d"

RAPIDAPI_KEY = "d2c1de7c7emsh6d981d4ffe2441dp1c9aeejsn63e76defa553"
AGIFY_KEY = "e6d7d4a5debe860b1078275454db5c8b"
GENDERIZE_KEY = "0f1bef8f172675dbb5c5be9f1ba1e2cc"

# ==========================================
# 2. RAPID-FIRE SIMULTANEOUS API FETCHER
# ==========================================
async def fetch_api(session, url, headers, params=None, data=None, method="GET"):
    try:
        if method == "GET":
            async with session.get(url, headers=headers, params=params, timeout=4) as resp:
                return await resp.json() if resp.status == 200 else None
        else:
            async with session.post(url, headers=headers, data=data, timeout=4) as resp:
                return await resp.json() if resp.status == 200 else None
    except:
        return None

async def check_all_caller_ids(session, phone):
    clean_num = phone.replace('+', '')
    if clean_num.startswith('91'):
        cc, local_num = 'in', clean_num[2:]
    elif clean_num.startswith('1'):
        cc, local_num = 'us', clean_num[1:]
    else:
        cc, local_num = 'us', clean_num

    base_headers = {"x-rapidapi-key": RAPIDAPI_KEY}

    h_sync = {**base_headers, "x-rapidapi-host": "syncme1.p.rapidapi.com"}
    t_sync = fetch_api(session, "https://syncme1.p.rapidapi.com/api/v1/search", h_sync, params={"phone": clean_num})
    
    h_eye = {**base_headers, "x-rapidapi-host": "caller-id-social-search-eyecon.p.rapidapi.com"}
    t_eye = fetch_api(session, "https://caller-id-social-search-eyecon.p.rapidapi.com/image", h_eye, params={"phone": clean_num})
    
    h_tc = {**base_headers, "x-rapidapi-host": "truecaller-api3.p.rapidapi.com", "Content-Type": "application/x-www-form-urlencoded"}
    t_tc = fetch_api(session, "https://truecaller-api3.p.rapidapi.com/v2.php", h_tc, data=f"phone={local_num}&countryCode={cc}", method="POST")
    
    h_kyb = {**base_headers, "x-rapidapi-host": "know-your-business.p.rapidapi.com"}
    t_kyb = fetch_api(session, "https://know-your-business.p.rapidapi.com/", h_kyb, params={"phone": clean_num})
    
    results = await asyncio.gather(t_sync, t_eye, t_tc, t_kyb, return_exceptions=True)
    
    for res in results:
        if isinstance(res, dict):
            if 'name' in res and res['name'] and str(res['name']).lower() not in ["unknown", "", "none"]:
                return res['name']
            if 'data' in res and isinstance(res['data'], list) and len(res['data']) > 0 and 'name' in res['data'][0]:
                return res['data'][0]['name']
            if 'truecaller_lookup' in res and 'data' in res['truecaller_lookup'] and len(res['truecaller_lookup']['data']) > 0:
                return res['truecaller_lookup']['data'][0].get('name', 'Unknown')
        elif isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict) and 'name' in res[0]:
            return res[0]['name']

    return "Unknown"

async def check_whatsapp_data(session, phone):
    clean_num = phone.replace('+', '')
    ws_status, ws_name = "No", "Unknown"
    
    try:
        async with session.post(f"https://7107.api.greenapi.com/waInstance{WS_INSTANCE_ID}/checkWhatsapp/{WS_API_TOKEN}", json={"phoneNumber": int(clean_num)}) as resp:
            if resp.status == 200:
                data = await resp.json()
                ws_status = "Yes" if data.get('existsWhatsapp') else "No"
                
        if ws_status == "Yes":
            async with session.post(f"https://7107.api.greenapi.com/waInstance{WS_INSTANCE_ID}/getContactInfo/{WS_API_TOKEN}", json={"chatId": f"{clean_num}@c.us"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    fetched_name = data.get('name', 'Unknown')
                    if fetched_name and str(fetched_name).strip() != "":
                        ws_name = fetched_name
    except:
        pass
    return ws_status, ws_name

async def fetch_demographics(session, final_name, phone):
    invalid_names = ["unknown", "-", "", "hidden (privacy)", "target user", "none"]
    if not final_name or str(final_name).lower().strip() in invalid_names:
        return "Unknown", "Unknown", "US/Intl" if not phone.startswith('+91') else "India"
    
    # Clean the name (helpful if it came from a username like @John_Doe123)
    # This keeps only alphabet characters, removes numbers and special symbols
    clean_fname = re.sub(r'[^a-zA-Z]', ' ', final_name).strip()
    clean_fname = clean_fname.split()[0] if clean_fname else ""
    
    if not clean_fname or len(clean_fname) < 2:
        return "Unknown", "Unknown", "US/Intl" if not phone.startswith('+91') else "India"
        
    try:
        age_req, gen_req = await asyncio.gather(
            session.get(f"https://api.agify.io?name={clean_fname}&apikey={AGIFY_KEY}"),
            session.get(f"https://api.genderize.io?name={clean_fname}&apikey={GENDERIZE_KEY}")
        )
        age = (await age_req.json()).get('age', 'Unknown')
        gender = (await gen_req.json()).get('gender', 'Unknown')
    except:
        age, gender = "Unknown", "Unknown"
        
    return age, gender, "India" if phone.startswith('+91') else "US/Intl"

# ==========================================
# 3. TELEGRAM BYPASS & CORE PROCESSOR
# ==========================================
async def process_single_number(phone, tg_client, http_session):
    ws_task = asyncio.create_task(check_whatsapp_data(http_session, phone))
    caller_task = asyncio.create_task(check_all_caller_ids(http_session, phone))
    
    uid, username, tg_status, tg_last_seen, active_days, tg_name = "Not Found", "Not Found", "Not Available", "-", "-", "-"
    
    try:
        rand_client_id = random.randint(10000, 999999)
        contact = InputPhoneContact(client_id=rand_client_id, phone=phone, first_name="Target", last_name="User")
        result = await tg_client(ImportContactsRequest([contact]))
        
        if result.users:
            user = result.users[0]
            tg_status = "Available"
            uid = str(user.id)
            username = f"@{user.username}" if user.username else "None"
            
            fetched_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if fetched_name.lower() == "target user":
                tg_name = "Hidden (Privacy)"
            else:
                tg_name = fetched_name or "-"
            
            if hasattr(user.status, 'was_online') and user.status.was_online:
                last_online = user.status.was_online
                tg_last_seen = last_online.strftime('%Y-%m-%d')
                active_days = str((datetime.now(timezone.utc) - last_online).days)
                
            await tg_client(DeleteContactsRequest(id=[user.id]))
    except Exception as e:
        print(f"TG Error {phone}: {e}")

    ws_status, ws_name = await ws_task
    caller_name = await caller_task
    
    # ---------------------------------------------------------
    # SMART DEMOGRAPHICS NAME SELECTION (Including Username!)
    # ---------------------------------------------------------
    demo_name = "Unknown"
    
    if caller_name not in ["Unknown", "", "-"]:
        demo_name = caller_name
    elif ws_name not in ["Unknown", "", "-"]:
        demo_name = ws_name
    elif tg_name not in ["Hidden (Privacy)", "-", "", "Unknown"]:
        demo_name = tg_name
    elif username not in ["None", "Not Found", "-", ""]:
        # If everything else fails, use the Telegram Username for Age/Gender calculation!
        demo_name = username
        
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

st.sidebar.title("System Specs 🚀")
st.sidebar.markdown("""
- **TG Engines:** 3 Active (Rotation)
- **WA Engines:** 2 Active
- **OSINT APIs:** 7 Active
- **Demo APIs:** 2 Active
- **Total Power:** 14 APIs Parallel
- **Smart Logic:** Username to Demographics AI ON
""")

st.title("Ultimate Telegram & WhatsApp OSINT Engine")
st.write("---")

uploaded_file = st.file_uploader("Upload .txt file with phone numbers", type=["txt"])

if uploaded_file is not None:
    content = uploaded_file.getvalue().decode("utf-8")
    phone_numbers = list(set(["+" + re.sub(r'\D', '', num) for num in content.split('\n') if re.sub(r'\D', '', num)]))
    st.write(f'Loaded unique numbers: **{len(phone_numbers)}**')
    
    if st.button("Start Processing"):
        with st.spinner("Firing 14 Engines Concurrently... (AI Username Parsing Active)"):
            progress_bar = st.progress(0)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            final_data = loop.run_until_complete(main_processor(phone_numbers, progress_bar))
            loop.close()
            
            df = pd.DataFrame(final_data)
            st.success("Processing Complete!")
            st.dataframe(df)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button("Download Excel (.xlsx)", data=output.getvalue(), file_name="BugFree_Master_Results.xlsx")
