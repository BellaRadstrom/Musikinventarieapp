import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import random

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="Musik-IT Birka v9", layout="wide")

# Initiera session states
if 'cart' not in st.session_state: st.session_state.cart = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'debug_log' not in st.session_state: st.session_state.debug_log = []

# --- 2. DATAHANTERING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_fresh_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        needed = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                  "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for c in needed:
            if c not in df.columns: df[c] = ""
        return df.fillna("")
    except Exception as e:
        return pd.DataFrame()

def sync_save(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        return True
    except:
        return False

if 'df' not in st.session_state:
    st.session_state.df = get_fresh_data()

# --- 3. HJÄLPFUNKTIONER ---
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

# --- 4. ADMIN & STATUS BANNER ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

# Visuell statusindikator högst upp
if is_admin:
    st.markdown("""
        <div style="background-color: #ff4b4b; padding: 10px; border-radius: 5px; text-align: center; color: white; font-weight: bold; margin-bottom: 20px;">
            🔴 ADMIN-LÄGE AKTIVERAT (Full behörighet)
        </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <div style="background-color: #28a745; padding: 10px; border-radius: 5px; text-align: center; color: white; font-weight: bold; margin-bottom: 20px;">
            🟢 ANVÄNDAR-LÄGE (Sök & Låna)
        </div>
    """, unsafe_allow_html=True)

# --- 5. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny produkt", "🔄 Återlämning", "⚙️ Admin"])

# --- 6. VY: SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    
    # --- EDITERINGSRUTA (Visas bara om admin klickat på Edit) ---
    if is_admin and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        row = st.session_state.df.loc[idx]
        
        with st.container(border=True):
            st.subheader(f"🛠️ Redigerar: {row['Modell']}")
            with st.form("edit_form_v9"):
                c1, c2 = st.columns(2)
                e_mod = c1.text_input("Modell", value=row['Modell'])
                e_brand = c1.text_input("Tillverkare", value=row['Tillverkare'])
                e_typ = c1.text_input("Typ", value=row['Typ'])
                e_status = c2.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], 
                                      index=["Tillgänglig", "Utlånad", "Service", "Trasig"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service", "Trasig"] else 0)
                e_owner = c2.text_input("Aktuell ägare", value=row['Aktuell ägare'])
                e_img = st.file_uploader("Byt ut bild")
                
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                save_btn = col_btn1.form_submit_button("💾 Spara")
                del_btn = col_btn2.form_submit_button("🗑️ Radera")
                cancel_btn = col_btn3.form_submit_button("❌ Avbryt")
                
                if save_btn:
                    df = get_fresh_data()
                    df.loc[idx, ['Modell', 'Tillverkare', 'Typ', 'Status', 'Aktuell ägare']] = [e_mod, e_brand, e_typ, e_status, e_owner]
                    if e_img: df.at[idx, 'Enhetsfoto'] = img_to_b64(e_img)
                    if sync_save(df):
                        st.session_state.df = df
                        st.session_state.edit_idx = None
                        st.rerun()
                
                if del_btn:
                    df = get_fresh_data()
                    df = df.drop(idx).reset_index(drop=True)
                    if sync_save(df):
                        st.session_state.df = df
                        st.session_state.edit_idx = None
                        st.rerun()
                
                if cancel_btn:
                    st.session_state.edit_idx = None
                    st.rerun()
        st.markdown("---")

    # --- SÖKFUNKTION ---
    q = st.text_input("Sök produkt/ID", value=st.query_params.get("q", ""))
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)] if q else st.session_state.df

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
                    if st.button("✏️ Editera", key=f"edit_trigger_{idx}"):
                        st.session_state.edit_idx = idx
                        st.rerun()

# (Resten av koden för Ny produkt, Återlämning och Admin förblir densamma som v8)
elif menu == "➕ Ny produkt":
    # ... (Samma som v8)
    pass
elif menu == "🔄 Återlämning":
    # ... (Samma som v8)
    pass
elif menu == "⚙️ Admin":
    # ... (Samma som v8)
    pass
