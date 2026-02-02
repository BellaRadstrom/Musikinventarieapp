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
st.set_page_config(page_title="Musik-IT Birka v13.5", layout="wide")

# Session states
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'cart' not in st.session_state: st.session_state.cart = []
if 'search_query' not in st.session_state: st.session_state.search_query = ""
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

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        return True
    except Exception as e:
        add_log(f"Save Error: {e}")
        return False

if 'df' not in st.session_state or st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. UTILITIES ---
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

def decode_qr_advanced(image_file):
    """Förbättrad QR-läsning med bildbehandling."""
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        
        # Förbehandling: Gråskala + Kontrastförstärkning
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        detector = cv2.QRCodeDetector()
        # Försök 1: Standard
        data, _, _ = detector.detectAndDecode(gray)
        
        # Försök 2: Om misslyckat, kör tröskelvärde (svartvitt)
        if not data:
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            data, _, _ = detector.detectAndDecode(thresh)
            
        return data.strip() if data else ""
    except Exception as e:
        add_log(f"Scan-logik-fel: {e}")
        return ""

# --- 4. SIDEBAR & ADMIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

# --- 5. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- 6. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    # QR-SKANNER EXPANDER
    with st.expander("📷 Starta QR-skanner", expanded=False):
        cam_image = st.camera_input("Rikta kameran mot QR-koden")
        if cam_image:
            found_id = decode_qr_advanced(cam_image)
            if found_id:
                st.session_state.search_query = found_id
                add_log(f"SKANNAT: Hittade '{found_id}'")
                st.success(f"Hittade ID: {found_id}")
                st.rerun()
            else:
                add_log("SKANNAT: Ingen kod hittades i bilden.")
                st.warning("Kunde inte läsa QR-koden. Försök hålla den stadigt och närmare.")

    # SÖKFÄLT
    q = st.text_input("Sök (Modell, ID, Färg...)", value=st.session_state.search_query)
    # Om användaren suddar manuellt, uppdatera state
    if q != st.session_state.search_query:
        st.session_state.search_query = q

    # SÖKRESULTAT & "INGET HITTAT"
    if st.session_state.search_query:
        sq = st.session_state.search_query
        # Filtrera (stöder partiell matchning på alla fält)
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(sq, case=False, na=False)).any(axis=1)]
        
        if results.empty:
            st.error(f"❌ Inget resultat i registret för: '{sq}'")
            if st.button("Rensa sökning"):
                st.session_state.search_query = ""
                st.rerun()
        else:
            st.info(f"Hittade {len(results)} matchningar.")
    else:
        results = st.session_state.df

    # VISA KORT
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

# --- 7. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    with st.form("new_v12", clear_on_submit=True):
        st.subheader("Lägg till ny utrustning")
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_tag = c2.text_input("ID (ÅÅMMDD-XXX) *")
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
    st.header("Individuell återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not borrowed.empty:
        owner = st.selectbox("Vem lämnar tillbaka?", ["---"] + list(borrowed['Aktuell ägare'].unique()))
        if owner != "---":
            items = borrowed[borrowed['Aktuell ägare'] == owner]
            for idx, row in items.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{row['Modell']}** (ID: {row['Resurstagg']})")
                    if c2.button("✅ Bekräfta", key=f"ret_{row['Resurstagg']}"):
                        df_upd = get_data_force()
                        p_idx = df_upd[df_upd['Resurstagg'] == row['Resurstagg']].index
                        df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                        if save_to_sheets(df_upd): 
                            st.session_state.df = df_upd
                            st.rerun()
    else: st.info("Inga utlånade produkter.")

# --- 9. ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    if is_admin:
        t1, t2 = st.tabs(["📋 Inventering", "📜 Logg"])
        with t1:
            st.dataframe(st.session_state.df)
        with t2:
            st.write("### Systemlogg")
            for l in reversed(st.session_state.debug_log): st.text(l)
