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

# CSS för design matchad mot din prototyp
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { background-color: #10b981; color: white; border-radius: 8px; border: none; width: 100%; }
    .stat-card { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS ANSLUTNING ---
# Din länk är nu inlagd här:
SHEET_URL = "https://docs.google.com/spreadsheets/d/1JGoN10kBJWJyIX0xzreVN0da0IFokP_LPNiMfYkB-b8/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Läser in data från ditt Google Sheet
        return conn.read(spreadsheet=SHEET_URL, ttl="0s")
    except Exception as e:
        # Om arket är helt tomt eller inte hittas, skapas grundstrukturen
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"]
        return pd.DataFrame(columns=cols)

def save_data(df):
    # Skriver tillbaka all data till Google Sheet
    conn.update(spreadsheet=SHEET_URL, data=df)
    st.cache_data.clear()

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Ladda data
df_raw = load_data()
if 'df' not in st.session_state or st.sidebar.button("🔄 Uppdatera data"):
    st.session_state.df = df_raw

if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    menu = st.radio("MENY", 
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "📝 Hantera & Redigera", "⚙️ System & Export"])
    st.write("---")
    st.success("🟢 Kopplad till Google Sheets")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    # Dashboard-statistik
    c1, c2, c3 = st.columns(3)
    total = len(st.session_state.df)
    avail = len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig']) if total > 0 else 0
    loaned = len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad']) if total > 0 else 0
    
    c1.markdown(f"<div class='stat-card'>Totalt<br><h2>{total}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{avail}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{loaned}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök på modell, tagg, ägare...")
    st.write("---")
    
    if total > 0:
        mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        filtered_df = st.session_state.df[mask]
        
        for idx, row in filtered_df.iterrows():
            r_img, r_info, r_qr, r_status, r_owner, r_action = st.columns([1, 2, 1, 1, 1, 1])
            
            with r_img:
                if pd.notnull(row['Enhetsfoto']) and str(row['Enhetsfoto']).startswith('http'):
                    st.image(row['Enhetsfoto'], width=60)
                else:
                    st.write("🖼️")
            
            r_info.write(f"**{row['Modell']}**\n\n{row['Tillverkare']}")
            
            qr_img = get_qr_image(row['Resurstagg'])
            buf = BytesIO()
            qr_img.save(buf, format="PNG")
            r_qr.image(buf, width=45)
            
            st_color = "#dcfce7" if row['Status'] == 'Tillgänglig' else "#fee2e2"
            r_status.markdown(f"<span style='background-color:{st_color}; padding:4px 8px; border-radius:10px;'>{row['Status']}</span>", unsafe_allow_html=True)
            r_owner.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) and row['Aktuell ägare'] != "" else "—")
            
            if row['Status'] == 'Tillgänglig':
                if r_action.button("➕ Låna", key=f"add_{idx}"):
                    if row['Resurstagg'] not in [c['Resurstagg'] for c in st.session_state.cart]:
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"✅ {row['Modell']} tillagd")
    else:
        st.info("Databasen är tom. Lägg till din första produkt i menyn till vänster.")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Registrera Ny Utrustning")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillv = col2.text_input("Tillverkare")
        tagg = col1.text_input("Resurstagg (Lämna tom för auto-ID)")
        foto = col2.text_input("Bild-URL (Länk till bild)")
        
        st.write("---")
        st.info("Använd kameran för att kontrollera utrustningen. För att spara bilden permanent i listan, klistra in en Bild-URL ovan.")
        cam = st.camera_input("Ta kontrollfoto")
        
        if st.form_submit_button("💾 SPARA PRODUKT"):
            if modell:
                final_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                new_row = {
                    "Enhetsfoto": foto, "Modell": modell, "Tillverkare": tillv, 
                    "Resurstagg": str(final_id), "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                # Uppdatera session och spara till Google
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"✅ Produkt sparad i Google Sheets med ID: {final_id}")
                st.balloons()
            else:
                st.error("Du måste ange en Modell.")

# --- VY: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Din Lånekorg")
    if not st.session_state.cart:
        st.info("Korgen är tom.")
    else:
        for item in st.session_state.cart:
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        
        name = st.text_input("Namn på låntagare *")
        date_loan = st.date_input("Utlåningsdatum", datetime.now())
        
        if st.button("🚀 GENOMFÖR UTLÅNING"):
            if name:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == str(item['Resurstagg']), ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, date_loan.strftime('%Y-%m-%d')]
                save_data(st.session_state.df)
                st.session_state.cart = []
                st.success(f"✅ Klart! Utlånat till {name}")
                st.rerun()
            else:
                st.error("Ange namn på låntagaren.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.selectbox("Välj föremål att returnera:", loaned['Modell'] + " [" + loaned['Resurstagg'].astype(str) + "]")
        if st.button("📥 REGISTRERA ÅTERLÄMNING"):
            tag = sel.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'].astype(str) == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', "", ""]
            save_data(st.session_state.df)
            st.success("✅ Instrumentet är nu tillgängligt igen.")
            st.rerun()
    else:
        st.info("Inga instrument är utlånade just nu.")

# --- VY: HANTERA & REDIGERA ---
elif menu == "📝 Hantera & Redigera":
    st.title("Redigera eller Radera")
    if not st.session_state.df.empty:
        sel = st.selectbox("Välj produkt:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'].astype(str) + "]")
        tag = sel.split("[")[1].split("]")[0]
        row = st.session_state.df[st.session_state.df['Resurstagg'].astype(str) == tag].iloc[0]
        
        with st.form("edit_form"):
            new_m = st.text_input("Modell", value=row['Modell'])
            new_t = st.text_input("Tillverkare", value=row['Tillverkare'])
            
            c_save, c_del = st.columns(2)
            if c_save.form_submit_button("💾 UPPDATERA"):
                st.session_state.df.loc[st.session_state.df['Resurstagg'].astype(str) == tag, ['Modell', 'Tillverkare']] = [new_m, new_t]
                save_data(st.session_state.df)
                st.success("Uppdaterad!")
                st.rerun()
            
            if c_del.form_submit_button("🗑️ RADERA PRODUKT"):
                st.session_state.df = st.session_state.df[st.session_state.df['Resurstagg'].astype(str) != tag]
                save_data(st.session_state.df)
                st.warning("Produkten raderad.")
                st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("Systeminställningar")
    st.write("Datan lagras säkert i Google Sheets.")
    st.link_button("📂 Öppna databasen i Google Sheets", SHEET_URL)
