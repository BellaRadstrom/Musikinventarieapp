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
    qr.add_data(str(data))
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
    st.success("🟢 System Status: Online")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat-card'>Totalt<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök...")
    st.write("---")
    
    h_img, h_info, h_qr, h_status, h_owner, h_action = st.columns([1, 2, 1, 1, 1, 1])
    h_img.caption("BILD")
    h_info.caption("INSTRUMENT")
    h_qr.caption("QR / ID")
    h_status.caption("STATUS")
    h_owner.caption("LÅNTAGARE")
    
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    for idx, row in st.session_state.df[mask].iterrows():
        r_img, r_info, r_qr, r_status, r_owner, r_action = st.columns([1, 2, 1, 1, 1, 1])
        
        with r_img:
            if pd.notnull(row['Enhetsfoto']) and str(row['Enhetsfoto']).startswith('http'):
                st.image(row['Enhetsfoto'], width=60)
            else:
                st.write("🖼️")
        
        r_info.write(f"**{row['Modell']}**")
        r_info.caption(row['Tillverkare'])
        
        qr_img = get_qr_image(row['Resurstagg'])
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        r_qr.image(buf, width=45)
        
        st_color = "#dcfce7" if row['Status'] == 'Tillgänglig' else "#fee2e2"
        r_status.markdown(f"<span style='background-color:{st_color}; padding:4px 8px; border-radius:10px;'>{row['Status']}</span>", unsafe_allow_html=True)
        r_owner.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
        
        if row['Status'] == 'Tillgänglig':
            if r_action.button("➕ Låna", key=f"add_{idx}"):
                if row['Resurstagg'] not in [c['Resurstagg'] for c in st.session_state.cart]:
                    st.session_state.cart.append(row.to_dict())
                    st.toast("Tillagd!")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Registrera Ny Utrustning")
    with st.form("add_form"):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillv = col2.text_input("Tillverkare")
        tagg = col1.text_input("Resurstagg (Lämna tom för auto-ID)")
        foto = col2.text_input("Bild-URL (valfritt)")
        
        cam = st.camera_input("Ta bild (ersätter URL)")
        
        if st.form_submit_button("💾 Spara"):
            if modell:
                final_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                new_row = {"Modell": modell, "Tillverkare": tillv, "Resurstagg": final_id, "Status": "Tillgänglig", "Enhetsfoto": foto}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"Sparad: {final_id}")
                st.rerun()

# --- VY: LÅNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Din Lånekorg")
    if not st.session_state.cart:
        st.info("Korgen är tom.")
    else:
        for item in st.session_state.cart:
            st.write(f"• {item['Modell']} ({item['Resurstagg']})")
        name = st.text_input("Låntagarens namn *")
        if st.button("🚀 Slutför utlåning") and name:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', name]
            save_data(st.session_state.df)
            st.session_state.cart = []
            st.success("Klart!")
            st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.selectbox("Välj instrument:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("📥 Returnera"):
            tag = sel.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', ""]
            save_data(st.session_state.df)
            st.rerun()

# --- VY: HANTERA & REDIGERA ---
elif menu == "📝 Hantera & Redigera":
    st.title("Redigera / Radera")
    sel = st.selectbox("Välj:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'] + "]")
    if sel:
        tag = sel.split("[")[1].split("]")[0]
        row = st.session_state.df[st.session_state.df['Resurstagg'] == tag].iloc[0]
        with st.form("edit"):
            m = st.text_input("Modell", value=row['Modell'])
            if st.form_submit_button("Spara"):
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, 'Modell'] = m
                save_data(st.session_state.df)
                st.rerun()
            if st.form_submit_button("🗑️ RADERA"):
                st.session_state.df = st.session_state.df[st.session_state.df['Resurstagg'] != tag]
                save_data(st.session_state.df)
                st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System & Export")
    st.download_button("📂 Ladda ner CSV", st.session_state.df.to_csv(index=False).encode('utf-8'), "data.csv")
