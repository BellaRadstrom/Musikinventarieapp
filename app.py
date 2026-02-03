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
st.set_page_config(page_title="Musik-IT Birka v15.5", layout="wide")

for key in ['cart', 'edit_idx', 'debug_log', 'last_loan', 'search_query', 'gen_id', 'cam_active_search', 'cam_active_reg']:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ['cart', 'debug_log'] else (False if 'cam_active' in key else "")

# --- 2. DATA CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data_force():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for c in cols:
            if c not in df.columns: df[c] = ""
        return df.fillna("")
    except:
        return pd.DataFrame()

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        st.session_state.df = df
        return True
    except:
        return False

if 'df' not in st.session_state or st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. UTILITIES ---
def generate_id(): 
    return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

def img_to_b64(file):
    if not file: return ""
    img = Image.open(file).convert("RGB")
    img.thumbnail((250, 250)) 
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=60, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

def get_qr_b64(data):
    qr = qrcode.make(str(data))
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- 4. SIDEBAR ---
st.sidebar.title("🎸 Musik-IT Birka")
is_admin = (st.sidebar.text_input("Admin lösenord", type="password") == "Birka")

# --- 5. VARUKORG ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart: st.caption(f"• {itm['Modell']}")
        borrower = st.text_input("Låntagarens namn *")
        if st.button("BEKRÄFTA LÅN", type="primary"):
            if borrower:
                df = get_data_force()
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = df[df['Resurstagg'] == itm['Resurstagg']].index
                    df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
                if save_to_sheets(df):
                    st.session_state.last_loan = {"name": borrower, "date": today, "items": st.session_state.cart.copy()}
                    st.session_state.cart = []
                    st.rerun()

# --- 6. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin"])

# --- 7. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li><b>{i['Modell']}</b></li>" for i in l['items']])
        st.components.v1.html(f"<div style='border:2px solid #333;padding:15px;background:white;'><h3>Lånekvitto: {l['name']}</h3><hr><ul>{rows}</ul><button onclick='window.print()'>SKRIV UT</button></div>", height=250)
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # iPad-Fix: Kameran laddas bara om användaren begär det
    if not st.session_state.cam_active_search:
        if st.button("📷 ÖPPNA QR-SKANNER"):
            st.session_state.cam_active_search = True
            st.rerun()
    else:
        if st.button("❌ STÄNG KAMERA"):
            st.session_state.cam_active_search = False
            st.rerun()
        cam_image = st.camera_input("Fota QR-kod")
        if cam_image:
            file_bytes = np.asarray(bytearray(cam_image.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, 1)
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img)
            if data:
                st.session_state.search_query = data.strip()
                st.session_state.cam_active_search = False
                st.rerun()

    q = st.text_input("Sök (Modell, ID...)", value=st.session_state.search_query)
    st.session_state.search_query = q
    
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)] if q else st.session_state.df

    for idx, row in results.head(20).iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig' and st.button("🛒", key=f"a{idx}"):
                    st.session_state.cart.append(row.to_dict())
                    st.toast("Tillagd!")

# --- 8. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    st.subheader("Registrera ny utrustning")
    if st.button("🔄 Generera ID & Streckkod"):
        st.session_state.gen_id = generate_id()
        st.rerun()

    with st.form("new_v15_5"):
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_typ = c1.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Övrigt"])
        f_tag = c2.text_input("ID *", value=st.session_state.gen_id)
        f_bc = c2.text_input("Streckkod", value=st.session_state.gen_id)
        
        # Kamera i formen kräver också manuell aktivering för iPad
        st.write("Foto kräver kamera-aktivering nedan.")
        submit = st.form_submit_button("✅ SPARA")
        
    # Kameran placeras utanför formen för att fungera bättre med iPad/Safari
    if not st.session_state.cam_active_reg:
        if st.button("📷 ÖPPNA KAMERA FÖR FOTO"):
            st.session_state.cam_active_reg = True
            st.rerun()
    else:
        f_foto = st.camera_input("Ta produktfoto")
        if f_foto:
            st.session_state.temp_foto = img_to_b64(f_foto)
            st.success("Foto sparat temporärt!")
            st.session_state.cam_active_reg = False
            
    if submit and f_mod and f_tag:
        df_current = get_data_force()
        new_row = {
            "Modell": f_mod, "Typ": f_typ, "Resurstagg": f_tag, "Streckkod": f_bc, 
            "Status": "Tillgänglig", "Enhetsfoto": st.session_state.get('temp_foto', ""),
            "Senast inventerad": datetime.now().strftime("%Y-%m-%d")
        }
        if save_to_sheets(pd.concat([df_current, pd.DataFrame([new_row])], ignore_index=True)):
            st.success("Sparad!")
            st.session_state.temp_foto = ""
            st.session_state.gen_id = ""

# --- 9. ÅTERLÄMNING & ADMIN (Förenklat för iPad-test) ---
elif menu == "🔄 Återlämning":
    st.write("Återlämning laddas...")
    # Samma logik som v15.4...
elif menu == "⚙️ Admin":
    if is_admin:
        st.dataframe(st.session_state.df)
