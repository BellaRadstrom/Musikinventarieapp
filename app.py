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
# Ersätt länken nedan med din egen länk från Google Sheets (Dela -> Alla med länken -> Redigerare)
SHEET_URL = "DIN_GOOGLE_SHEET_URL_HÄR"

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        return conn.read(spreadsheet=SHEET_URL, ttl="0s")
    except:
        # Om arket är helt tomt, skapa grundstrukturen
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"]
        return pd.DataFrame(columns=cols)

def save_data(df):
    conn.update(spreadsheet=SHEET_URL, data=df)
    st.cache_data.clear()

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Ladda data till sessionen
st.session_state.df = load_data()

if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    menu = st.radio("MENY", 
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "📝 Hantera & Redigera", "⚙️ System & Export"])
    st.write("---")
    st.success("🟢 System: Google Cloud Sync")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    # Dashboard
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat-card'>Totalt<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök på modell, tagg, ägare...")
    st.write("---")
    
    # Lista
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
        r_owner.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
        
        if row['Status'] == 'Tillgänglig':
            if r_action.button("➕ Låna", key=f"add_{idx}"):
                if row['Resurstagg'] not in [c['Resurstagg'] for c in st.session_state.cart]:
                    st.session_state.cart.append(row.to_dict())
                    st.toast(f"✅ {row['Modell']} i korgen")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Registrera Ny Utrustning")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillv = col2.text_input("Tillverkare")
        tagg = col1.text_input("Resurstagg (Lämna tom för auto-ID)")
        foto = col2.text_input("Bild-URL")
        
        st.write("---")
        cam = st.camera_input("Ta kontrollfoto (Sparas ej permanent i molnet)")
        
        if st.form_submit_button("💾 SPARA I GOOGLE SHEETS"):
            if modell:
                final_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                new_row = {
                    "Enhetsfoto": foto, "Modell": modell, "Tillverkare": tillv, 
                    "Resurstagg": final_id, "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"✅ Sparad permanent i Google Sheets!")
                st.balloons()
            else:
                st.error("Modell saknas!")

# --- VY: LÅNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Lånekorg")
    if not st.session_state.cart:
        st.info("Korgen är tom.")
    else:
        for item in st.session_state.cart:
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        
        name = st.text_input("Vem lånar? *")
        date_loan = st.date_input("Datum", datetime.now())
        
        if st.button("🚀 GENOMFÖR UTLÅNING"):
            if name:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, date_loan.strftime('%Y-%m-%d')]
                save_data(st.session_state.df)
                st.session_state.cart = []
                st.success("✅ Utlånat och sparat!")
                st.rerun()
            else:
                st.error("Ange ett namn!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.selectbox("Välj återlämning:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("📥 REGISTRERA RETUR"):
            tag = sel.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', "", ""]
            save_data(st.session_state.df)
            st.success("Återställd!")
            st.rerun()
    else:
        st.info("Inga utlånade föremål.")

# --- VY: HANTERA & REDIGERA ---
elif menu == "📝 Hantera & Redigera":
    st.title("Redigera / Radera")
    if not st.session_state.df.empty:
        sel = st.selectbox("Välj objekt:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'] + "]")
        tag = sel.split("[")[1].split("]")[0]
        row = st.session_state.df[st.session_state.df['Resurstagg'] == tag].iloc[0]
        
        with st.form("edit"):
            new_m = st.text_input("Modell", value=row['Modell'])
            new_t = st.text_input("Tillverkare", value=row['Tillverkare'])
            if st.form_submit_button("💾 UPPDATERA"):
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Modell', 'Tillverkare']] = [new_m, new_t]
                save_data(st.session_state.df)
                st.success("Uppdaterad!")
                st.rerun()
            if st.form_submit_button("🗑️ RADERA PERMANENT"):
                st.session_state.df = st.session_state.df[st.session_state.df['Resurstagg'] != tag]
                save_data(st.session_state.df)
                st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System")
    st.write("All data sparas i realtid till Google Sheets.")
    st.link_button("📂 Öppna Google Sheets-databas", SHEET_URL)
    
    st.divider()
    st.subheader("Ladda ner QR för utskrift (3x4 cm)")
    target = st.selectbox("Välj produkt för QR:", st.session_state.df['Modell'] + " (" + st.session_state.df['Resurstagg'] + ")")
    if target:
        tag_qr = target.split("(")[1].replace(")", "")
        img = get_qr_image(tag_qr)
        st.image(img, width=150)
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.download_button("📥 Ladda ner QR-bild", buf.getvalue(), f"QR_{tag_qr}.png")
