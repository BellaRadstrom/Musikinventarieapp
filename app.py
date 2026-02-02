import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import random
import cv2  # Ny import för QR-läsning
import numpy as np

# --- 1. SETUP ---
st.set_page_config(page_title="Musik-IT Birka v13", layout="wide")

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
    """Avkodar QR-kod från en bildfil."""
    file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
    opencv_image = cv2.imdecode(file_bytes, 1)
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(opencv_image)
    return data

# --- 4. ADMIN STATUS BANNER ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

if is_admin:
    st.markdown("<div style='background:#ff4b4b;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🔴 ADMIN-LÄGE AKTIVERAT</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background:#28a745;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🟢 ANVÄNDAR-LÄGE</div>", unsafe_allow_html=True)

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
    # 1. Visa kvitto om ett lån precis gjorts
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li><b>{i['Modell']}</b><br><small>ID: {i['Resurstagg']}</small></li>" for i in l['items']])
        st.components.v1.html(f"<div style='border:2px solid #333;padding:15px;background:white;font-family:sans-serif;'><h3>Lånekvitto: {l['name']}</h3><p>Datum: {l['date']}</p><hr><ul>{rows}</ul><button onclick='window.print()'>🖨️ SKRIV UT</button></div>", height=300)
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # 2. QR-SKANNER (Inställning för att direkt uppdatera sökfältet)
    with st.expander("📷 Starta QR-skanner", expanded=False):
        # Vi lägger till en unik nyckel för att kunna återställa kameran om det behövs
        cam_image = st.camera_input("Ta en bild på QR-koden för att skanna")
        
        if cam_image:
            scanned_code = decode_qr(cam_image)
            if scanned_code:
                st.success(f"Hittade ID: {scanned_code}")
                # Viktigt: Uppdatera session_state direkt
                st.session_state.search_query = scanned_code
                add_log(f"QR Skannad: {scanned_code}")
                # Tvinga omladdning så att sökfältet fångar upp värdet direkt
                st.rerun()
            else:
                st.error("Kunde inte läsa QR-koden. Försök hålla kameran närmare eller stabilare.")

    # 3. SÖKFÄLT (Styrs av session_state)
    # Vi använder en callback eller direkt tilldelning för att synka manuell sökning och skanning
    search_val = st.text_input("Sök (Modell, ID, Färg...)", 
                               value=st.session_state.get('search_query', ""),
                               key="search_input")
    
    # Uppdatera session_state om användaren skriver manuellt
    st.session_state.search_query = search_val

    # 4. SÖKLOGIK OCH RESULTAT
    if st.session_state.search_query:
        q = st.session_state.search_query
        # Sök i alla kolumner
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
        
        if results.empty:
            st.warning(f"⚠️ Inga produkter hittades som matchar '{q}'.")
            # Knapp för att rensa sökning
            if st.button("Rensa sökning"):
                st.session_state.search_query = ""
                st.rerun()
        else:
            st.info(f"Hittade {len(results)} matchningar.")
    else:
        results = st.session_state.df

    # 5. RENDERA RESULTATKORT
    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: 
                    st.image(row['Enhetsfoto'], width=100)
                else:
                    st.caption("Ingen bild")
                # QR-kod för etikett-referens
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=60)
            
            with c2:
                st.subheader(row['Modell'])
                st.write(f"**ID:** {row['Resurstagg']}")
                st.write(f"**Typ:** {row['Typ']} | **Färg:** {row['Färg']}")
                
                # Status-indikator
                status = row['Status']
                if status == 'Tillgänglig':
                    st.markdown(f"🟢 **Status:** {status}")
                elif status == 'Utlånad':
                    st.markdown(f"🔴 **Status:** {status} till **{row['Aktuell ägare']}**")
                    st.caption(f"Utlånat: {row['Utlåningsdatum']}")
                else:
                    st.markdown(f"🟡 **Status:** {status}")

            with c3:
                # Knappar baserat på status
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg i varukorg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"{row['Modell']} tillagd!")
                        st.rerun()
                
                if is_admin:
                    if st.button("✏️ Editera", key=f"edit_{idx}"):
                        st.session_state.edit_idx = idx
                        st.rerun()
