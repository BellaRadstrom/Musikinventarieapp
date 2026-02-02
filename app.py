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
st.set_page_config(page_title="Musik-IT Birka v13.3", layout="wide")

# Session states
for key in ['cart', 'edit_idx', 'debug_log', 'last_loan', 'search_query']:
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
        add_log(f"Data hämtad: {len(df)} rader.")
        return df.fillna("")
    except Exception as e:
        add_log(f"Fetch Error: {e}")
        return pd.DataFrame()

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        add_log("Data sparad till Sheets.")
        return True
    except Exception as e:
        add_log(f"Save Error: {e}")
        return False

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

def decode_qr(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        opencv_image = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(opencv_image)
        # Rensa eventuella osynliga tecken
        return data.strip() if data else ""
    except Exception as e:
        add_log(f"QR Scan Error: {e}")
        return ""

# --- 4. ADMIN STATUS ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

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
                    st.session_state.cart = []; st.session_state.df = df; st.rerun()
            else: st.error("Namn krävs!")

# --- 6. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- 7. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li><b>{i['Modell']}</b><br><small>ID: {i['Resurstagg']}</small></li>" for i in l['items']])
        st.components.v1.html(f"<div style='border:2px solid #333;padding:15px;background:white;font-family:sans-serif;'><h3>Lånekvitto: {l['name']}</h3><p>Datum: {l['date']}</p><hr><ul>{rows}</ul><button onclick='window.print()'>🖨️ SKRIV UT</button></div>", height=300)
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # QR-SKANNER
    with st.expander("📷 Starta QR-skanner", expanded=False):
        cam_image = st.camera_input("Rikta kameran mot QR-koden")
        if cam_image:
            found_id = decode_qr(cam_image)
            if found_id:
                add_log(f"KAMERA: Hittade koden '{found_id}'")
                st.session_state.search_query = found_id
                st.success(f"Identifierade ID: {found_id}")
                st.rerun()
            else:
                add_log("KAMERA: Bild tagen men ingen kod kunde avkodas.")
                st.warning("Ingen QR-kod hittades i bilden.")

    # EDITERING (Säkerhetscheckad)
    if is_admin and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        if idx in st.session_state.df.index:
            row = st.session_state.df.loc[idx]
            with st.container(border=True):
                st.subheader(f"🛠️ Editera: {row['Modell']}")
                with st.form("edit_v13"):
                    c1, c2 = st.columns(2)
                    e_mod = c1.text_input("Modell", row['Modell'])
                    e_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Trasig", "Utlånad"], index=0)
                    e_img_cam = st.camera_input("Uppdatera foto")
                    if st.form_submit_button("Spara"):
                        df = get_data_force()
                        df.loc[idx, ['Modell', 'Status']] = [e_mod, e_status]
                        if e_img_cam: df.at[idx, 'Enhetsfoto'] = img_to_b64(e_img_cam)
                        save_to_sheets(df); st.session_state.edit_idx = None; st.rerun()
                    if st.form_submit_button("Avbryt"): st.session_state.edit_idx = None; st.rerun()
        else: st.session_state.edit_idx = None

    # SÖKFÄLT
    q = st.text_input("Sök (Modell, ID, Färg...)", value=st.session_state.search_query)
    st.session_state.search_query = q # Synka manuell sökning tillbaka till state

    # FILTRERING & LOGGNING
    if q:
        add_log(f"FILTER: Söker efter '{q}'")
        # Sök i hela dataframe
        mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False, na=False)).any(axis=1)
        results = st.session_state.df[mask]
        add_log(f"FILTER: Hittade {len(results)} matchningar.")
        
        if results.empty:
            st.warning(f"Ingen produkt med ID/namn '{q}' hittades i registret.")
            if st.button("Visa alla produkter igen"):
                st.session_state.search_query = ""
                st.rerun()
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
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"a{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"e{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- 8. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    with st.form("new_v12", clear_on_submit=True):
        st.subheader("Lägg till ny utrustning")
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_tag_val = st.session_state.get('gen_id', "")
        f_tag = c2.text_input("ID (ÅÅMMDD-XXX) *", value=f_tag_val)
        if c2.form_submit_button("🔄 Generera ID"):
            st.session_state.gen_id = generate_id(); st.rerun()
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        f_foto = st.camera_input("Ta foto")
        if st.form_submit_button("✅ SPARA"):
            if f_mod and f_tag:
                df = get_data_force()
                new = {"Modell": f_mod, "Resurstagg": f_tag, "Status": f_status, 
                       "Enhetsfoto": img_to_b64(f_foto) if f_foto else "", "Senast inventerad": datetime.now().strftime("%Y-%m-%d")}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                if save_to_sheets(df): st.rerun()

# --- 9. ÅTERLÄMNING ---
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
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{row['Modell']}** (ID: {row['Resurstagg']})")
                    if c2.button("✅ Bekräfta återkomst", key=f"ret_{row['Resurstagg']}"):
                        df_upd = get_data_force()
                        p_idx = df_upd[df_upd['Resurstagg'] == row['Resurstagg']].index
                        df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = ['Tillgänglig', '', '', datetime.now().strftime("%Y-%m-%d")]
                        if save_to_sheets(df_upd): st.session_state.df = df_upd; st.rerun()
    else: st.info("Inga utlånade produkter.")

# --- 10. ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    if is_admin:
        t1, t2, t3 = st.tabs(["📋 Inventering", "🖨️ Bulk QR", "📜 Logg"])
        with t1:
            st.subheader(f"Inventering {datetime.now().strftime('%Y-%m-%d')}")
            st.dataframe(st.session_state.df[['Modell', 'Resurstagg', 'Status', 'Senast inventerad']])
        with t2:
            st.write("Bulk QR-generering här.")
        with t3:
            st.write("### Systemlogg (Felsökning)")
            for l in reversed(st.session_state.debug_log): st.text(l)
