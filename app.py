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
st.set_page_config(page_title="Musik-IT Birka v15.4", layout="wide")

# Session states
for key in ['cart', 'edit_idx', 'debug_log', 'last_loan', 'search_query', 'gen_id']:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ['cart', 'debug_log'] else ""

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
        st.session_state.df = df
        add_log("Data sparad till Sheets.")
        return True
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")
        return False

if 'df' not in st.session_state or st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. UTILITIES ---
def generate_id(): 
    return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

def img_to_b64(file):
    """iPad-optimerad bildkomprimering"""
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

# --- 4. SIDEBAR & ADMIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password", key="sidebar_pwd")
is_admin = (pwd == "Birka")

if is_admin:
    st.markdown("<div style='background:#ff4b4b;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🔴 ADMIN-LÄGE AKTIVERAT</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background:#28a745;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🟢 ANVÄNDAR-LÄGE</div>", unsafe_allow_html=True)

# --- 5. VARUKORG ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart: st.caption(f"• {itm['Modell']}")
        borrower = st.text_input("Låntagarens namn *", key="cart_borrower")
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
                    st.success("Lånet har registrerats!")
                    st.rerun()

# --- 6. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- 7. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li><b>{i['Modell']}</b><br><small>Märke: {i['Tillverkare']} | ID: {i['Resurstagg']}</small></li>" for i in l['items']])
        st.components.v1.html(f"<div style='border:2px solid #333;padding:15px;background:white;font-family:sans-serif;'><h3>Lånekvitto: {l['name']}</h3><p>Datum: {l['date']}</p><hr><ul>{rows}</ul><button onclick='window.print()'>🖨️ SKRIV UT</button></div>", height=300)
        if st.button("Stäng kvitto & Rensa"): st.session_state.last_loan = None; st.rerun()

    with st.expander("📷 ÖPPNA QR-SKANNER", expanded=False):
        cam_image = st.camera_input("Fota QR-kod", key="search_cam")
        if cam_image:
            scanned = decode_qr_logic(cam_image)
            if scanned:
                if scanned != st.session_state.search_query:
                    st.session_state.search_query = scanned
                    st.session_state.edit_idx = None
                    st.toast(f"Hittade ID: {scanned}")
                    st.rerun()

    if is_admin and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        if idx in st.session_state.df.index:
            row = st.session_state.df.loc[idx]
            with st.container(border=True):
                st.subheader(f"🛠️ Editera: {row['Modell']}")
                with st.form("edit_v15_4"):
                    c1, c2 = st.columns(2)
                    e_mod = c1.text_input("Modell", row['Modell'])
                    e_brand = c1.text_input("Tillverkare", row['Tillverkare'])
                    e_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Trasig", "Utlånad"], index=0)
                    e_owner = c2.text_input("Ägare", row['Aktuell ägare'])
                    e_img_cam = st.camera_input("Uppdatera foto", key="edit_cam")
                    
                    b1, b2, b3 = st.columns(3)
                    if b1.form_submit_button("Spara"):
                        df = get_data_force()
                        df.loc[idx, ['Modell', 'Tillverkare', 'Status', 'Aktuell ägare']] = [e_mod, e_brand, e_status, e_owner]
                        if e_img_cam: df.at[idx, 'Enhetsfoto'] = img_to_b64(e_img_cam)
                        if save_to_sheets(df):
                            st.success("Ändringar sparade!")
                            st.session_state.edit_idx = None
                            st.rerun()
                    if b2.form_submit_button("Radera 🗑️"):
                        df = get_data_force()
                        df = df.drop(idx).reset_index(drop=True)
                        if save_to_sheets(df):
                            st.session_state.edit_idx = None
                            st.rerun()
                    if b3.form_submit_button("Avbryt"): st.session_state.edit_idx = None; st.rerun()
        else:
            st.session_state.edit_idx = None

    q_input = st.text_input("Sök (Modell, ID, Färg...)", value=st.session_state.search_query)
    if q_input != st.session_state.search_query:
        st.session_state.search_query = q_input
        st.session_state.edit_idx = None
    
    if st.session_state.search_query:
        if st.button("❌ Rensa sökning"):
            st.session_state.search_query = ""
            st.session_state.edit_idx = None
            st.rerun()

    q = st.session_state.search_query
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)] if q else st.session_state.df

    # Visningsbegränsning för iPad-minne
    max_visible = 20
    for idx, row in results.head(max_visible).iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=120)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=60)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                if row['Status'] == 'Utlånad': st.error(f"Låntagare: {row['Aktuell ägare']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"a{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Tillagd!")
                        st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"e{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()
    if len(results) > max_visible:
        st.info(f"Visar de {max_visible} första träffarna. Förfina sökningen för att se mer.")

# --- 8. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    st.subheader("Registrera ny utrustning")
    if st.button("🔄 Generera ID & Streckkod"):
        st.session_state.gen_id = generate_id()
        st.rerun()

    with st.form("new_v15_4", clear_on_submit=True):
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_typ = c1.selectbox("Typ av produkt", ["Instrument", "PA", "Mikrofoner", "Övrigt"])
        f_farg = c1.text_input("Färg")
        f_tag = c2.text_input("Resurstagg (ID) *", value=st.session_state.gen_id)
        f_bc = c2.text_input("Streckkod", value=st.session_state.gen_id)
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        f_foto = st.camera_input("Ta foto", key="new_reg_cam")
        
        if st.form_submit_button("✅ SPARA TILL DATABAS"):
            if f_mod and f_tag:
                df_current = get_data_force()
                new_row = {
                    "Modell": f_mod, "Tillverkare": f_brand, "Typ": f_typ, "Färg": f_farg, 
                    "Resurstagg": f_tag, "Streckkod": f_bc, "Status": f_status, 
                    "Enhetsfoto": img_to_b64(f_foto) if f_foto else "", 
                    "Senast inventerad": datetime.now().strftime("%Y-%m-%d"),
                    "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                if save_to_sheets(pd.concat([df_current, pd.DataFrame([new_row])], ignore_index=True)):
                    st.success(f"{f_mod} har sparats!")
                    st.session_state.gen_id = ""
                else:
                    st.error("Kunde inte spara.")
            else:
                st.warning("Fyll i Modell och Resurstagg!")

# --- 9. ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Individuell återlämning")
    borrowed = get_data_force()[get_data_force()['Status'] == 'Utlånad']
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
                        df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = ['Tillgänglig', '', '', datetime.now().strftime("%Y-%m-%d")]
                        if save_to_sheets(df_upd):
                            st.success("Återställd!")
                            st.rerun()
    else: st.info("Inga utlånade produkter.")

# --- 10. ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    if is_admin:
        if st.button("🚨 TVINGA SYNK", type="primary", use_container_width=True):
            st.session_state.df = get_data_force()
            st.success("Synkad!")
            st.rerun()
        t1, t2, t3 = st.tabs(["📋 Inventering", "🖨️ Bulk QR", "📜 Logg"])
        with t1:
            st.dataframe(st.session_state.df[['Modell', 'Resurstagg', 'Status', 'Aktuell ägare']])
        with t2:
            sel = st.multiselect("Välj för utskrift", st.session_state.df['Modell'].tolist())
            if sel:
                html = "<div style='display:flex;flex-wrap:wrap;gap:5px;'>"
                for m in sel:
                    r = st.session_state.df[st.session_state.df['Modell'] == m].iloc[0]
                    qr_img = get_qr_b64(r['Resurstagg'])
                    html += f"<div style='width:3cm;height:4cm;border:1px solid #ccc;text-align:center;padding:5px;'><img src='data:image/png;base64,{qr_img}' style='width:2.5cm;'><br><b style='font-size:10px;'>{r['Modell']}</b></div>"
                st.components.v1.html(html + "</div><br><button onclick='window.print()'>SKRIV UT</button>", height=500)
        with t3:
            for l in reversed(st.session_state.debug_log): st.text(l)
