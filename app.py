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

# --- 1. SETUP & SESSION STATE ---
st.set_page_config(page_title="Musik-IT Birka v16.6.1", layout="wide")

# Initiera alla session states direkt vid start för att undvika KeyError
initial_states = {
    'cart': [],
    'edit_idx': None,
    'debug_log': [],
    'last_loan': None,
    'search_query': "",
    'gen_id': "",
    'cam_active': False,
    'inv_check': {},
    'df': None,
    'temp_img': ""
}

for key, value in initial_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{ts}] {msg}")

# --- 2. DATA CONNECTION ---
# SÄKERHET: Hämta lösenord
try:
    ADMIN_PWD = st.secrets.get("admin_password", "Birka")
except:
    ADMIN_PWD = "Birka"

conn = st.connection("gsheets", type=GSheetsConnection)

def get_data_force():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        # Säkerställ att kritiska kolumner finns
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad", "Notering"]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df.fillna("")
    except Exception as e:
        st.error(f"Kunde inte hämta data: {e}")
        return pd.DataFrame()

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        st.session_state.df = df
        return True
    except Exception as e:
        st.error(f"Fel vid sparning: {e}")
        return False

# Ladda data om det inte finns
if st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. HJÄLPFUNKTIONER ---
def generate_id(): 
    return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

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

# --- 4. SIDEBAR ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == ADMIN_PWD)

if is_admin:
    st.markdown("<div style='background:#ff4b4b;padding:10px;border-radius:5px;text-align:center;color:white;'>🔴 ADMIN-LÄGE</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background:#28a745;padding:10px;border-radius:5px;text-align:center;color:white;'>🟢 ANVÄNDAR-LÄGE</div>", unsafe_allow_html=True)

# Varukorg i sidebar
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart:
            st.caption(f"• {itm['Modell']}")
        borrower = st.text_input("Låntagarens namn", key="borrow_name")
        if st.button("BEKRÄFTA LÅN"):
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

# --- 5. MENYVAL ---
menu = st.sidebar.selectbox("Välj funktion", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- 6. LOGIK FÖR SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li>{i['Modell']} ({i['Resurstagg']})</li>" for i in l['items']])
        st.info(f"Senaste lån: {l['name']} - {l['date']}")
        if st.button("Rensa kvitto"): st.session_state.last_loan = None; st.rerun()

    q = st.text_input("Sök i registret...", value=st.session_state.search_query)
    st.session_state.search_query = q
    
    df_view = st.session_state.df
    if q:
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]

    for idx, row in df_view.head(20).iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
            with c2:
                st.markdown(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | Typ: {row['Typ']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("Lägg till", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("Ändra", key=f"edit_{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- 7. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    st.subheader("Lägg till ny utrustning")
    with st.form("new_item"):
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell")
        f_typ = c1.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Kablage", "Ljus", "Övrigt"])
        f_tag = c2.text_input("Resurstagg", value=generate_id())
        f_stat = c2.selectbox("Status", ["Tillgänglig", "Reserv", "Service"])
        if st.form_submit_button("Spara"):
            df_now = get_data_force()
            new_data = {"Modell": f_mod, "Typ": f_typ, "Resurstagg": f_tag, "Status": f_stat, "Senast inventerad": datetime.now().strftime("%Y-%m-%d")}
            if save_to_sheets(pd.concat([df_now, pd.DataFrame([new_data])], ignore_index=True)):
                st.success("Sparad!"); st.rerun()

# --- 8. ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    df_ret = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not df_ret.empty:
        for idx, row in df_ret.iterrows():
            st.write(f"**{row['Modell']}** - Lånad av: {row['Aktuell ägare']}")
            if st.button("Återlämna", key=f"ret_{idx}"):
                full_df = get_data_force()
                full_df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                if save_to_sheets(full_df): st.rerun()
    else:
        st.info("Inga utlånade produkter.")

# --- 9. ADMIN & INVENTERING (HÄR ÄR DINA NYA FUNKTIONER) ---
elif menu == "⚙️ Admin & Inventering":
    if not is_admin:
        st.warning("Vänligen ange admin-lösenord i sidomenyn.")
    else:
        t1, t2, t3 = st.tabs(["🖨️ QR-utskrift", "📜 Lagerlistor", "📋 Logg"])
        
        with t1:
            st.subheader("Bulk-utskrift av QR")
            types = list(st.session_state.df['Typ'].unique())
            sel_type = st.multiselect("Välj typer att skriva ut", types)
            if st.button("Generera QR-ark"):
                df_qrs = st.session_state.df[st.session_state.df['Typ'].isin(sel_type)] if sel_type else st.session_state.df
                html = "<div style='display:flex;flex-wrap:wrap;gap:15px;'>"
                for _, r in df_qrs.iterrows():
                    qrb64 = get_qr_b64(r['Resurstagg'])
                    html += f"<div style='border:1px solid #eee;padding:10px;text-align:center;'><img src='data:image/png;base64,{qrb64}' width='100'><br><small>{r['Modell']}</small></div>"
                st.components.v1.html(html + "</div><br><button onclick='window.print()'>Skriv ut</button>", height=500)

        with t2:
            st.subheader("Inventeringsunderlag")
            c1, c2 = st.columns(2)
            l_type = c1.selectbox("Filtrera på typ", ["Alla"] + list(st.session_state.df['Typ'].unique()))
            l_stat = c2.multiselect("Visa status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], default=["Tillgänglig", "Utlånad"])
            
            if st.button("Visa lista"):
                df_l = st.session_state.df.copy()
                if l_type != "Alla": df_l = df_l[df_l['Typ'] == l_type]
                df_l = df_l[df_l['Status'].isin(l_stat)]
                
                table = "<table><thead><tr><th>Modell</th><th>ID</th><th>Status</th><th>Info</th></tr></thead><tbody>"
                for _, r in df_l.iterrows():
                    info = f"Lånad av: {r['Aktuell ägare']}" if r['Status'] == 'Utlånad' else ""
                    table += f"<tr><td>{r['Modell']}</td><td>{r['Resurstagg']}</td><td>{r['Status']}</td><td>{info}</td></tr>"
                st.markdown(table + "</tbody></table>", unsafe_allow_html=True)
                st.button("🖨️ Skriv ut (Ctrl+P)")

        with t3:
            st.write(st.session_state.debug_log)
