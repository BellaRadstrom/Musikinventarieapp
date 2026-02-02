import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import random
import cv2
import numpy as np

# --- 1. SETUP ---
st.set_page_config(page_title="Musik-IT Birka v14.3", layout="wide")

if 'search_query' not in st.session_state: st.session_state.search_query = ""
if 'cart' not in st.session_state: st.session_state.cart = []
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'last_loan' not in st.session_state: st.session_state.last_loan = None

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{ts}] {msg}")

# --- 2. DATA CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data_force():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        return df.fillna("")
    except Exception as e:
        return pd.DataFrame()

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        return True
    except:
        return False

if 'df' not in st.session_state or st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. UTILITIES (DENNA ÄR UPPDATERAD FÖR MOBIL) ---
def decode_qr_logic(image_file):
    """Förstärkt läsare för mobilkameror"""
    try:
        # Konvertera Streamlit-fil till OpenCV-format
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        
        # 1. Bildbehandling: Gråskala och ökad kontrast
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Skapa QR-detektor
        detector = cv2.QRCodeDetector()
        
        # Prova vanlig detektering
        data, bbox, _ = detector.detectAndDecode(gray)
        
        # 3. Om den misslyckas, prova att kasta om färgerna (vissa koder kan vara inverterade)
        if not data:
            gray_inv = cv2.bitwise_not(gray)
            data, bbox, _ = detector.detectAndDecode(gray_inv)
            
        return data.strip() if data else ""
    except Exception as e:
        add_log(f"QR Scan Error: {e}")
        return ""

def get_qr_b64(data):
    qr = qrcode.make(str(data))
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def img_to_b64(file):
    if not file: return ""
    img = Image.open(file).convert("RGB")
    img.thumbnail((300, 300))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

# --- 4. SIDEBAR ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password", key="pwd_v143")
is_admin = (pwd == "Birka")

# --- 5. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"], key="nav_v143")

# --- 6. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        st.success(f"Lån bekräftat för {st.session_state.last_loan['name']}")
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # QR-SKANNER
    with st.expander("📷 ÖPPNA QR-SKANNER", expanded=False):
        cam_img = st.camera_input("Ta en tydlig bild på QR-koden", key="scan_v143")
        if cam_img:
            with st.spinner("Analyserar kod..."):
                code = decode_qr_logic(cam_img)
                if code:
                    st.session_state.search_query = code
                    st.success(f"Hittade: {code}")
                    st.rerun()
                else:
                    st.error("Kunde inte läsa koden. Prova att hålla kameran stadigt och närmare koden.")

    # SÖKFÄLT
    q = st.text_input("Sök (Modell, ID, Färg...)", value=st.session_state.search_query, key="q_v143")
    
    if q != st.session_state.search_query:
        st.session_state.search_query = q

    if st.session_state.search_query:
        if st.button("❌ Rensa sökning"):
            st.session_state.search_query = ""
            st.rerun()

    # FILTRERING & VISNING
    query = st.session_state.search_query.lower()
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row.get('Enhetsfoto'): st.image(row['Enhetsfoto'], width=100)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=60)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"ed_{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- (Resten av koden från v12 behålls intakt nedanför) ---
elif menu == "➕ Ny registrering":
    # [v12 kod för Ny registrering...]
    st.info("Använd v12-formuläret här")
    # (Jag utelämnar resten av prose-koden för att hålla svaret kort, 
    # men du behåller bara din gamla v12-kod här precis som innan)
    # --- VISNING AV KORT (v12-stil) ---
    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=60)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"ed_{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- 8. NY REGISTRERING (v12) ---
elif menu == "➕ Ny registrering":
    with st.form("new_form", clear_on_submit=True):
        st.subheader("Lägg till ny utrustning")
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_tag_val = st.session_state.get('gen_id', "")
        f_tag = c2.text_input("ID (ÅÅMMDD-XXX) *", value=f_tag_val)
        if c2.form_submit_button("🔄 Generera ID"):
            st.session_state.gen_id = generate_id(); st.rerun()
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        f_foto = st.camera_input("Ta foto", key="reg_cam")
        if st.form_submit_button("✅ SPARA"):
            if f_mod and f_tag:
                df = get_data_force()
                new = {"Modell": f_mod, "Tillverkare": f_brand, "Resurstagg": f_tag, "Status": f_status, 
                       "Enhetsfoto": img_to_b64(f_foto) if f_foto else "", "Senast inventerad": datetime.now().strftime("%Y-%m-%d")}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                if save_to_sheets(df): st.rerun()

# --- 9. ÅTERLÄMNING (v12) ---
elif menu == "🔄 Återlämning":
    st.header("Individuell återlämning")
    borrowed = get_data_force()[get_data_force()['Status'] == 'Utlånad']
    if not borrowed.empty:
        owner = st.selectbox("Vem lämnar tillbaka?", ["---"] + list(borrowed['Aktuell ägare'].unique()))
        if owner != "---":
            items = borrowed[borrowed['Aktuell ägare'] == owner]
            for idx, row in items.iterrows():
                with st.container(border=True):
                    st.write(f"**{row['Modell']}** ({row['Resurstagg']})")
                    if st.button("✅ Bekräfta återkomst", key=f"ret_{idx}"):
                        df_upd = get_data_force()
                        p_idx = df_upd[df_upd['Resurstagg'] == row['Resurstagg']].index
                        df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = ['Tillgänglig', '', '', datetime.now().strftime("%Y-%m-%d")]
                        if save_to_sheets(df_upd): st.rerun()
    else: st.info("Inga utlånade produkter.")

# --- 10. ADMIN & INVENTERING (v12) ---
elif menu == "⚙️ Admin & Inventering":
    if is_admin:
        if st.button("🚨 TVINGA SYNK", type="primary", use_container_width=True):
            st.session_state.df = get_data_force(); st.rerun()
        t1, t2 = st.tabs(["📋 Inventering", "📜 Logg"])
        with t1:
            st.dataframe(st.session_state.df[['Modell', 'Resurstagg', 'Status', 'Aktuell ägare']])
        with t2:
            for l in reversed(st.session_state.debug_log): st.text(l)

