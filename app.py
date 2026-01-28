import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
import os
from datetime import datetime
import random

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="InstrumentDB", layout="wide")
DB_FILE = "Musikinventarie.csv"

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { background-color: #10b981; color: white; border-radius: 8px; border: none; width: 100%; }
    .stat-card { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .instrument-img { border-radius: 8px; object-fit: cover; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA-HANTERING ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"]
    return pd.DataFrame(columns=cols)

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    menu = st.radio("MENY", 
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "📝 Hantera & Redigera", "⚙️ System & Export"])
    st.write("---")
    st.success("🟢 System Status: Säker anslutning")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    # Statistik
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat-card'>Totalt antal<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök på modell, tillverkare, tagg...")
    
    st.write("---")
    # Header för listan
    h_img, h_info, h_qr, h_status, h_owner, h_action = st.columns([1, 2, 1, 1, 1, 1])
    h_img.caption("BILD")
    h_info.caption("INSTRUMENT")
    h_qr.caption("QR / ID")
    h_status.caption("STATUS")
    h_owner.caption("LÅNTAGARE")
    h_action.caption("ÅTGÄRD")

    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    filtered_df = st.session_state.df[mask]
    
    for idx, row in filtered_df.iterrows():
        r_img, r_info, r_qr, r_status, r_owner, r_action = st.columns([1, 2, 1, 1, 1, 1])
        
        # 1. Miniatyrbild
        with r_img:
            photo_url = row.get('Enhetsfoto', '')
            if pd.notnull(photo_url) and str(photo_url).startswith('http'):
                st.image(photo_url, width=70)
            else:
                # En enkel ikon/bild om URL saknas
                st.write("🖼️")
        
        # 2. Instrument info
        r_info.write(f"**{row['Modell']}**")
        r_info.caption(f"{row['Tillverkare']} • {row['Typ']}")
        
        # 3. QR & Tagg
        qr_img = get_qr_image(row['Resurstagg'])
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        r_qr.image(buf, width=45)
        r_qr.caption(row['Resurstagg'])
        
        # 4. Status
        st_color = "#dcfce7" if row['Status'] == 'Tillgänglig' else "#fee2e2"
        txt_color = "#166534" if row['Status'] == 'Tillgänglig' else "#991b1b"
        r_status.markdown(f"<span style='background-color:{st_color}; color:{txt_color}; padding:4px 10px; border-radius:12px; font-size:11px;'>{row['Status']}</span>", unsafe_allow_html=True)
        
        # 5. Ägare
        r_owner.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) and row['Aktuell ägare'] != "" else "—")
        
        # 6. Knappar
        if row['Status'] == 'Tillgänglig':
            if r_action.button("➕ Låna", key=f"add_{idx}"):
                if row['Resurstagg'] not in [c['Resurstagg'] for c in st.session_state.cart]:
                    st.session_state.cart.append(row.to_dict())
                    st.toast("Tillagd i korg!")

# --- (Övriga funktioner som Lägg till, Lånekorg, Återlämning, Redigera förblir desamma) ---
# ... (Se föregående koder för fullständiga funktioner under elif/else)
