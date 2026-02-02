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
st.set_page_config(page_title="Musik-IT Birka v14.0", layout="wide")

# Initiera alla session states centralt
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
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for c in cols:
            if c not in df.columns: df[c] = ""
        return df.fillna("")
    except Exception as e:
        add_log(f"Fetch Error: {e}")
        return pd.DataFrame()

if 'df' not in st.session_state or st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. UTILITIES ---
def generate_id(): return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

def img_to_b64(file):
    if not file: return ""
    img = Image.open(file).convert("RGB")
    img.thumbnail((300, 300))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

def get_qr_b64(data):
    qr = qrcode.make(str(data))
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def decode_qr_mobile(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(gray)
        return data.strip() if data else ""
    except Exception as e:
        add_log(f"QR Error: {e}")
        return ""

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        add_log("Data sparad till Sheets.")
        return True
    except Exception as e:
        add_log(f"Save Error: {e}")
        return False

# --- 4. NAVIGATION & ADMIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password", key="sidebar_pwd_14")
is_admin = (pwd == "Birka")

if is_admin:
    st.markdown("<div style='background:#ff4b4b;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🔴 ADMIN-LÄGE</div>", unsafe_allow_html=True)

menu = st.sidebar.selectbox(
    "Meny", 
    ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"],
    key="sidebar_menu_14"
)

# --- 5. VARUKORG ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart: st.caption(f"• {itm['Modell']}")
        borrower = st.text_input("Låntagarens namn *", key="borrower_name")
        if st.button("BEKRÄFTA LÅN", type="primary", key="confirm_loan"):
            if borrower:
                df = get_data_force()
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = df[df['Resurstagg'] == itm['Resurstagg']].index
                    df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
                if save_to_sheets(df):
                    st.session_state.last_loan = {"name": borrower, "date": today, "items": st.session_state.cart.copy()}
                    st.session_state.cart = []; st.session_state.df = df; st.rerun()

# --- 6. HUVUDMENY: SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    # Kvitto-visning
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        st.success(f"Lån registrerat på {l['name']}!")
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # QR-Skanner
    with st.expander("📷 ÖPPNA QR-SKANNER", expanded=False):
        cam_image = st.camera_input("Rikta kameran mot koden", key="qr_cam_14")
        if cam_image:
            scanned = decode_qr_mobile(cam_image)
            if scanned:
                st.session_state.search_query = scanned
                add_log(f"Skannat: {scanned}")
                st.rerun() # Tvingar sökningen att ske direkt

    # Sökfält
    q_input = st.text_input("Sök (Modell, ID, Färg...)", value=st.session_state.search_query, key="search_field_14")
    
    if q_input != st.session_state.search_query:
        st.session_state.search_query = q_input

    if st.session_state.search_query:
        if st.button("❌ Rensa sökning", key="clear_btn_14"):
            st.session_state.search_query = ""
            st.rerun()

    # Filtrering
    q = st.session_state.search_query.lower()
    if q:
        results = st.session_state.df[st.session_state.df.astype(str).apply(
            lambda x: x.str.contains(q, case=False, na=False)).any(axis=1)]
    else:
        results = st.session_state.df

    # Visa Kort
    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=60)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                if row['Status'] == 'Utlånad': st.error(f"Låntagare: {row['Aktuell ägare']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"edit_{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- 7. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    with st.form("new_reg_form", clear_on_submit=True):
        st.subheader("Registrera ny utrustning")
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_tag_val = st.session_state.get('gen_id', "")
        f_tag = c2.text_input("ID (ÅÅMMDD-XXX) *", value=f_tag_val)
        if c2.form_submit_button("🔄 Generera ID"):
            st.session_state.gen_id = generate_id(); st.rerun()
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        f_foto = st.camera_input("Ta foto")
        if st.form_submit_button("✅ SPARA"):
            if f_mod and f_tag:
                df = get_data_force()
                new = {"Modell": f_mod, "Tillverkare": f_brand, "Resurstagg": f_tag, "Status": f_status, 
                       "Enhetsfoto": img_to_b64(f_foto) if f_foto else "", "Senast inventerad": datetime.now().strftime("%Y-%m-%d")}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                if save_to_sheets(df): st.rerun()

# --- 8. ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not borrowed.empty:
        owner = st.selectbox("Vem lämnar tillbaka?", ["---"] + list(borrowed['Aktuell ägare'].unique()), key="ret_owner")
        if owner != "---":
            items = borrowed[borrowed['Aktuell ägare'] == owner]
            for idx, row in items.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{row['Modell']}** (ID: {row['Resurstagg']})")
                    if c2.button("✅ Bekräfta", key=f"ret_btn_{idx}"):
                        df_upd = get_data_force()
                        p_idx = df_upd[df_upd['Resurstagg'] == row['Resurstagg']].index
                        df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                        if save_to_sheets(df_upd): 
                            st.session_state.df = df_upd; st.rerun()
    else: st.info("Inga utlånade produkter.")

# --- 9. ADMIN ---
elif menu == "⚙️ Admin & Inventering":
    if is_admin:
        if st.button("🚨 TVINGA SYNK", use_container_width=True):
            st.session_state.df = get_data_force(); st.rerun()
        t1, t2 = st.tabs(["📋 Inventering", "📜 Logg"])
        with t1:
            st.dataframe(st.session_state.df[['Modell', 'Resurstagg', 'Status', 'Aktuell ägare', 'Senast inventerad']])
        with t2:
            for l in reversed(st.session_state.debug_log): st.text(l)
