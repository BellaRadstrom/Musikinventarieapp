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
st.set_page_config(page_title="Musik-IT Birka v14.4", layout="wide")

# Session states (v12 + sökstöd)
if 'cart' not in st.session_state: st.session_state.cart = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'last_loan' not in st.session_state: st.session_state.last_loan = None
if 'search_query' not in st.session_state: st.session_state.search_query = ""

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{ts}] {msg}")

# --- 2. DATA CONNECTION (v12 Original) ---
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

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        add_log("Data skickad till Sheets.")
        return True
    except Exception as e:
        add_log(f"Save Error: {e}")
        return False

# Initial laddning
if 'df' not in st.session_state:
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

def decode_qr_logic(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(gray)
        return data.strip() if data else ""
    except:
        return ""

# --- 4. ADMIN & SIDEBAR ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password", key="pwd_v14")
is_admin = (pwd == "Birka")

if is_admin:
    st.sidebar.success("🔴 ADMIN-LÄGE")
else:
    st.sidebar.info("🟢 ANVÄNDAR-LÄGE")

# --- 5. VARUKORG ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart: st.caption(f"• {itm['Modell']}")
        borrower = st.text_input("Låntagarens namn *", key="bt_name")
        if st.button("BEKRÄFTA LÅN", type="primary"):
            if borrower:
                df = get_data_force()
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = df[df['Resurstagg'] == itm['Resurstagg']].index
                    df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
                if save_to_sheets(df):
                    st.session_state.last_loan = {"name": borrower, "date": today, "items": st.session_state.cart.copy()}
                    st.session_state.cart = []; st.session_state.df = df; st.rerun()

# --- 6. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"], key="main_menu")

# --- 7. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        st.success(f"Lån registrerat: {l['name']}")
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # QR-SKANNER (Med Loop-skydd)
    with st.expander("📷 ÖPPNA QR-SKANNER", expanded=False):
        cam_image = st.camera_input("Fota QR-kod", key="cam_input")
        if cam_image:
            scanned = decode_qr_logic(cam_image)
            if scanned:
                # VIKTIGT: Endast uppdatera om det är ett NYTT id för att bryta loopen
                if scanned != st.session_state.search_query:
                    st.session_state.search_query = scanned
                    st.rerun()

    # SÖKFÄLT (v12 stil)
    q = st.text_input("Sök (Modell, ID, Färg...)", value=st.session_state.search_query)
    
    # Uppdatera state om man skriver manuellt
    if q != st.session_state.search_query:
        st.session_state.search_query = q

    if st.session_state.search_query:
        if st.button("❌ Rensa sökning"):
            st.session_state.search_query = ""
            st.rerun()

    # FILTRERING (v12 exakt kopia)
    if st.session_state.search_query:
        query = st.session_state.search_query.lower()
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
    else:
        results = st.session_state.df

    # VISNING AV KORT (v12 exakt kopia)
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
                    if st.button("🛒 Lägg till", key=f"a{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"e{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- 8. NY REGISTRERING (v12) ---
elif menu == "➕ Ny registrering":
    with st.form("new_v12", clear_on_submit=True):
        st.subheader("Lägg till ny utrustning")
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_typ = c1.text_input("Typ")
        f_farg = c1.text_input("Färg")
        f_tag_val = st.session_state.get('gen_id', "")
        f_tag = c2.text_input("ID (ÅÅMMDD-XXX) *", value=f_tag_val)
        if c2.form_submit_button("🔄 Generera ID"):
            st.session_state.gen_id = generate_id(); st.rerun()
        f_bc = c2.text_input("Streckkod")
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        f_foto = st.camera_input("Ta foto")
        if st.form_submit_button("✅ SPARA"):
            if f_mod and f_tag:
                df = get_data_force()
                new = {"Modell": f_mod, "Tillverkare": f_brand, "Typ": f_typ, "Färg": f_farg, 
                       "Resurstagg": f_tag, "Streckkod": f_bc, "Status": f_status, 
                       "Enhetsfoto": img_to_b64(f_foto) if f_foto else "", "Senast inventerad": datetime.now().strftime("%Y-%m-%d")}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                if save_to_sheets(df): st.rerun()

# --- 9. ÅTERLÄMNING (v12) ---
elif menu == "🔄 Återlämning":
    st.header("Individuell återlämning")
    current_df = get_data_force()
    borrowed = current_df[current_df['Status'] == 'Utlånad']
    if not borrowed.empty:
        owner = st.selectbox("Vem lämnar tillbaka?", ["---"] + list(borrowed['Aktuell ägare'].unique()))
        if owner != "---":
            items = borrowed[borrowed['Aktuell ägare'] == owner]
            for idx, row in items.iterrows():
                with st.container(border=True):
                    st.write(f"**{row['Modell']}** (ID: {row['Resurstagg']})")
                    if st.button("✅ Bekräfta", key=f"ret_{idx}"):
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
            st.subheader(f"Inventeringsstatus {datetime.now().strftime('%Y-%m-%d')}")
            st.dataframe(st.session_state.df[['Modell', 'Resurstagg', 'Status', 'Aktuell ägare']])
        with t2:
            for l in reversed(st.session_state.debug_log): st.text(l)
