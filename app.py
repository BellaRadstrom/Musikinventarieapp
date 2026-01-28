import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from datetime import datetime
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# CSS för att snygga till gränssnittet
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; }
    .status-tag { padding: 4px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- ANSLUTNINGSFUNKTION ---
def get_clean_connection():
    try:
        # Vi anropar anslutningen utan extra parametrar för att undvika "multiple values"-felet.
        # Den hämtar automatiskt allt (inkl. spreadsheet-URL) från din Secrets.
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Kopplingsfel: {e}")
        return None

conn = get_clean_connection()

# --- DATAFUNKTIONER ---
def load_data():
    if conn:
        try:
            # Hämtar data direkt från molnet utan cache för att alltid se senaste
            return conn.read(ttl="0s")
        except Exception as e:
            st.session_state.error_log = str(e)
    return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Aktuell ägare"])

# Initiera sessionstate för att spara data lokalt mellan klick
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 Musikinventering")
    menu = st.radio("MENY", [
        "🔍 Sök & Inventarie", 
        "➕ Lägg till (Kamera)", 
        "🛒 Lånekorg", 
        "🔄 Återlämning", 
        "⚙️ System & Diagnostik"
    ])
    st.write("---")
    if st.button("🔄 Uppdatera från molnet"):
        st.session_state.df = load_data()
        st.rerun()

# --- VY 1: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Instrumentregister")
    df = st.session_state.df
    
    if not df.empty:
        search = st.text_input("Sök i registret", placeholder="Sök på modell, märke eller ID...")
        # Filtrera datan
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        filtered_df = df[mask]
        
        for idx, row in filtered_df.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.markdown(f"**{row['Modell']}**\n*{row.get('Tillverkare', 'Okänd')}*")
                c2.write(f"ID: {row['Resurstagg']}")
                
                status = str(row.get('Status', 'Tillgänglig'))
                status_color = "#dcfce7" if status == "Tillgänglig" else "#fee2e2"
                c3.markdown(f'<span class="status-tag" style="background-color:{status_color};">{status}</span>', unsafe_allow_html=True)
                
                if status == "Tillgänglig":
                    if c4.button("Låna", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"{row['Modell']} tillagd i korgen!")
                else:
                    c4.write(f"👤 {row.get('Aktuell ägare', 'Lånad')}")
            st.divider()
    else:
        st.info("Ingen data hittades. Lägg till ditt första instrument eller kolla 'System' för fel.")

# --- VY 2: LÄGG TILL (MED KAMERA) ---
elif menu == "➕ Lägg till (Kamera)":
    st.title("Registrera ny utrustning")
    with st.form("add_instrument_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        new_modell = col1.text_input("Modellnamn *")
        new_tillv = col2.text_input("Tillverkare/Märke")
        new_tagg = col1.text_input("Resurstagg / Streckkod")
        
        st.write("---")
        # Kamerafunktionen
        captured_photo = st.camera_input("Ta en bild på instrumentet")
        
        if st.form_submit_button("Spara instrument"):
            if new_modell:
                final_tag = new_tagg if new_tagg else f"ID-{random.randint(1000, 9999)}"
                new_row = {
                    "Modell": new_modell,
                    "Tillverkare": new_tillv,
                    "Resurstagg": str(final_tag),
                    "Status": "Tillgänglig",
                    "Aktuell ägare": ""
                }
                # Lägg till i listan och spara till Google
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if conn:
                    try:
                        conn.update(data=st.session_state.df)
                        st.success(f"✅ {new_modell} har sparats i molnet!")
                        # Om man tog ett foto kan man spara ner det (valfritt steg för senare)
                    except Exception as e:
                        st.error(f"Kunde inte spara till Google Sheets: {e}")
            else:
                st.error("Du måste minst fylla i ett modellnamn.")

# --- VY 3: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Utlåning")
    if st.session_state.cart:
        st.write("Följande föremål förbereds för utlån:")
        for i, item in enumerate(st.session_state.cart):
            st.write(f"{i+1}. **{item['Modell']}** (ID: {item['Resurstagg']})")
        
        borrower_name = st.text_input("Låntagarens namn *")
        
        col_a, col_b = st.columns(2)
        if col_a.button("Töm korgen"):
            st.session_state.cart = []
            st.rerun()
            
        if col_b.button("🚀 Bekräfta utlån"):
            if borrower_name:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', borrower_name]
                
                if conn:
                    conn.update(data=st.session_state.df)
                    st.session_state.cart = []
                    st.success(f"Klart! Allt registrerat på {borrower_name}.")
                    st.rerun()
            else:
                st.warning("Ange ett namn på låntagaren.")
    else:
        st.info("Korgen är tom. Gå till 'Sök & Inventarie' för att välja instrument.")

# --- VY 4: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned_items = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    
    if not loaned_items.empty:
        selected_to_return = st.selectbox(
            "Välj instrument som lämnas tillbaka:", 
            loaned_items['Modell'] + " [" + loaned_items['Resurstagg'] + "]"
        )
        
        if st.button("📥 Registrera återlämning"):
            # Extrahera ID:t inifrån klamrarna [ID]
            tag_to_fix = selected_to_return.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag_to_fix, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            
            if conn:
                conn.update(data=st.session_state.df)
                st.success("Instrumentet är nu tillgängligt igen!")
                st.rerun()
    else:
        st.info("Inga instrument är markerade som utlånade just nu.")

# --- VY 5: SYSTEM & DIAGNOSTIK ---
elif menu == "⚙️ System & Diagnostik":
    st.title("Systemstatus")
    
    if 'error_log' in st.session_state:
        st.error(f"Tekniskt fel vid inläsning: {st.session_state.error_log}")
    else:
        st.success("✅ Kopplingen till Google Sheets är aktiv och fungerar.")
    
    st.write("---")
    st.subheader("Rådata (direkt från Google Sheets)")
    st.dataframe(st.session_state.df)
    
    if st.button("Radera all lokal cache"):
        st.cache_data.clear()
        st.rerun()
