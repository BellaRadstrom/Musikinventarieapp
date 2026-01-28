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
# Nu hämtas allt (URL och inloggning) från Secrets automatiskt
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # ttl="0s" tvingar appen att hämta ny data varje gång istället för att använda gammal cache
        return conn.read(ttl="0s")
    except Exception as e:
        st.error(f"Kunde inte hämta data: {e}")
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"]
        return pd.DataFrame(columns=cols)

def save_data(df):
    try:
        conn.update(data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Kunde inte spara till Google Sheets: {e}")
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
    
    st.write("---")
    st.success("🟢 Inloggad via Service Account")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    c1, c2, c3 = st.columns(3)
    total = len(st.session_state.df)
    avail = len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig']) if total > 0 else 0
    loaned = len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad']) if total > 0 else 0
    
    c1.markdown(f"<div class='stat-card'>Totalt i listan<br><h2>{total}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Ledigt</span><br><h2>{avail}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånat</span><br><h2>{loaned}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök...")
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
            
            r_info.write(f"**{row['Modell']}**\n{row.get('Tillverkare', '')}")
            
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
                        st.toast(f"✅ Lagt till {row['Modell']}")
    else:
        st.info("Ingen data hittades i Google Sheets.")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Lägg till ny produkt")
    with st.form("add_form", clear_on_submit=True):
        modell = st.text_input("Modell *")
        tillv = st.text_input("Tillverkare")
        tagg = st.text_input("Resurstagg (Lämna tom för slumpat ID)")
        foto = st.text_input("Bild-URL")
        
        if st.form_submit_button("💾 SPARA PERMANENT"):
            if modell:
                final_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                new_row = {
                    "Enhetsfoto": foto, "Modell": modell, "Tillverkare": tillv, 
                    "Resurstagg": str(final_id), "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"Sparad i molnet med ID: {final_id}")
                    st.balloons()
            else:
                st.error("Du måste fylla i modell!")

# --- VY: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Dina valda instrument")
    if not st.session_state.cart:
        st.info("Korgen är tom.")
    else:
        for item in st.session_state.cart:
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        
        name = st.text_input("Låntagarens namn *")
        if st.button("🚀 GENOMFÖR LÅN"):
            if name:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == str(item['Resurstagg']), ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, datetime.now().strftime('%Y-%m-%d')]
                if save_data(st.session_state.df):
                    st.session_state.cart = []
                    st.success("Lånet sparat i Google Sheets!")
                    st.rerun()
            else:
                st.error("Namn saknas!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Registrera retur")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.selectbox("Välj instrument:", loaned['Modell'] + " [" + loaned['Resurstagg'].astype(str) + "]")
        if st.button("📥 TA EMOT RETUR"):
            tag = sel.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'].astype(str) == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', "", ""]
            if save_data(st.session_state.df):
                st.success("Retur registrerad!")
                st.rerun()
    else:
        st.info("Inga utlånade föremål.")

# --- VY: HANTERA & REDIGERA ---
elif menu == "📝 Hantera & Redigera":
    st.title("Redigera databas")
    if not st.session_state.df.empty:
        sel = st.selectbox("Välj instrument:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'].astype(str) + "]")
        tag = sel.split("[")[1].split("]")[0]
        row = st.session_state.df[st.session_state.df['Resurstagg'].astype(str) == tag].iloc[0]
        
        with st.form("edit"):
            new_m = st.text_input("Modell", value=row['Modell'])
            if st.form_submit_button("💾 UPPDATERA"):
                st.session_state.df.loc[st.session_state.df['Resurstagg'].astype(str) == tag, 'Modell'] = new_m
                save_data(st.session_state.df)
                st.success("Uppdaterad!")
                st.rerun()
            if st.form_submit_button("🗑️ RADERA"):
                st.session_state.df = st.session_state.df[st.session_state.df['Resurstagg'].astype(str) != tag]
                save_data(st.session_state.df)
                st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System")
    st.write("Datan lagras i Google Sheets.")
    # Vi kan inte visa länken enkelt härifrån utan att lägga till den i Secrets också under ett annat namn,
    # men du vet ju var ditt ark finns!
