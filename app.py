import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from datetime import datetime
import random

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { background-color: #10b981; color: white; border-radius: 8px; border: none; width: 100%; }
    .stat-card { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS ANSLUTNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(ttl="0s")
        if data is None or data.empty:
            return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])
        return data
    except Exception as e:
        st.error(f"Kopplingsfel: {e}")
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        conn.update(data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")
        return False

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Initiera data
if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    menu = st.radio("MENY", 
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "📝 Hantera & Redigera", "⚙️ System & Export"])
    
    if st.button("🔄 Synka med Google Sheets"):
        st.session_state.df = load_data()
        st.rerun()

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    df = st.session_state.df
    
    c1, c2, c3 = st.columns(3)
    total = len(df)
    avail = len(df[df['Status'] == 'Tillgänglig']) if total > 0 else 0
    loaned = len(df[df['Status'] == 'Utlånad']) if total > 0 else 0
    
    c1.markdown(f"<div class='stat-card'>Totalt<br><h2>{total}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Ledigt</span><br><h2>{avail}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånat</span><br><h2>{loaned}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök...")
    
    if total > 0:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            r_img, r_info, r_qr, r_status, r_owner, r_action = st.columns([1, 2, 1, 1, 1, 1])
            with r_img:
                if pd.notnull(row['Enhetsfoto']) and str(row['Enhetsfoto']).startswith('http'):
                    st.image(row['Enhetsfoto'], width=60)
                else: st.write("🖼️")
            r_info.write(f"**{row['Modell']}**")
            qr_img = get_qr_image(row['Resurstagg'])
            buf = BytesIO()
            qr_img.save(buf, format="PNG")
            r_qr.image(buf, width=45)
            st_color = "#dcfce7" if row['Status'] == 'Tillgänglig' else "#fee2e2"
            r_status.markdown(f"<span style='background-color:{st_color}; padding:4px 8px; border-radius:10px;'>{row['Status']}</span>", unsafe_allow_html=True)
            r_owner.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
            if row['Status'] == 'Tillgänglig':
                if r_action.button("➕ Låna", key=f"add_{idx}"):
                    st.session_state.cart.append(row.to_dict())
                    st.toast("Tillagd!")
    else:
        st.info("Tomt i registret.")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Registrera Ny")
    with st.form("add_form", clear_on_submit=True):
        modell = st.text_input("Modell *")
        tillv = st.text_input("Tillverkare")
        tagg = st.text_input("ID/Tagg")
        if st.form_submit_button("💾 SPARA"):
            if modell:
                final_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                new_row = {"Modell": modell, "Tillverkare": tillv, "Resurstagg": str(final_id), "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparad!")

# --- VY: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Lånekorg")
    if not st.session_state.cart:
        st.info("Korgen är tom.")
    else:
        for item in st.session_state.cart:
            st.write(f"• {item['Modell']}")
        borrower = st.text_input("Namn *")
        if st.button("🚀 BEKRÄFTA"):
            if borrower:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == str(item['Resurstagg']), ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, datetime.now().strftime('%Y-%m-%d')]
                save_data(st.session_state.df)
                st.session_state.cart = []
                st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'].astype(str) + "]")
        if st.button("📥 RETUR"):
            tag = sel.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'].astype(str) == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', "", ""]
            save_data(st.session_state.df)
            st.rerun()

# --- VY: HANTERA & REDIGERA ---
elif menu == "📝 Hantera & Redigera":
    st.title("Redigera")
    if not st.session_state.df.empty:
        sel = st.selectbox("Välj:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'].astype(str) + "]")
        tag = sel.split("[")[1].split("]")[0]
        if st.button("🗑️ RADERA"):
            st.session_state.df = st.session_state.df[st.session_state.df['Resurstagg'].astype(str) != tag]
            save_data(st.session_state.df)
            st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System")
    st.dataframe(st.session_state.df)
