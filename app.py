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
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "⚙️ System & Export"])
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

    search = st.text_input("", placeholder="Sök på modell, tagg eller ägare...")
    
    st.write("---")
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    filtered_df = st.session_state.df[mask]
    
    for idx, row in filtered_df.iterrows():
        r1, r2, r3, r4, r5 = st.columns([2, 1, 1, 1, 1])
        r1.write(f"**{row['Modell']}**\n\n{row['Tillverkare']}")
        
        # QR
        qr_img = get_qr_image(row['Resurstagg'])
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        r2.image(buf, width=50)
        r2.caption(row['Resurstagg'])
        
        r3.write(row['Status'])
        r4.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
        
        if row['Status'] == 'Tillgänglig':
            if r5.button("➕ Lägg i korg", key=f"add_{idx}"):
                if row['Resurstagg'] not in [c['Resurstagg'] for c in st.session_state.cart]:
                    st.session_state.cart.append(row.to_dict())
                    st.toast("Tillagd i korg!")

# --- VY: LÄGG TILL (AUTOMATISKT ID) ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Lägg till musikutrustning")
    
    with st.form("add_form"):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillverkare = col2.text_input("Tillverkare")
        
        # Automatgenererat ID om tomt
        tagg_input = col1.text_input("Resurstagg (Lämna tom för automatiskt ID)")
        sn = col2.text_input("Serienummer")
        
        st.write("---")
        st.subheader("Foto")
        cam_image = st.camera_input("Ta en bild")
        
        if st.form_submit_button("💾 Spara musikutrustning"):
            if modell:
                # Generera ID om det saknas
                final_tagg = tagg_input if tagg_input else f"ID-{datetime.now().strftime('%y%m%d')}-{random.randint(1000, 9999)}"
                
                new_data = {
                    "Modell": modell,
                    "Tillverkare": tillverkare,
                    "Resurstagg": final_tagg,
                    "Streckkod": final_tagg,
                    "Serienummer": sn,
                    "Status": "Tillgänglig",
                    "Aktuell ägare": "",
                    "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"✅ Sparad med ID: {final_tagg}")
            else:
                st.error("Modell måste fyllas i!")

# --- VY: LÅNEKORG (TVINGANDE NAMN & DATUM) ---
elif menu == "🛒 Lånekorg":
    st.title("Lånekorg")
    
    if not st.session_state.cart:
        st.info("Korgen är tom. Gå till 'Sök & Inventarie' för att lägga till instrument.")
    else:
        st.write("### Produkter i korgen:")
        for item in st.session_state.cart:
            st.write(f"✅ {item['Modell']} ({item['Resurstagg']})")
        
        st.write("---")
        borrower_name = st.text_input("Namn på låntagare *")
        loan_date = st.date_input("Utlåningsdatum", datetime.now())
        
        if st.button("🚀 Slutför utlåning"):
            if borrower_name:
                for item in st.session_state.cart:
                    # Uppdatera status i stora tabellen
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 'Status'] = 'Utlånad'
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 'Aktuell ägare'] = borrower_name
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 'Utlåningsdatum'] = loan_date.strftime("%Y-%m-%d")
                
                save_data(st.session_state.df)
                st.session_state.cart = [] # Töm korgen
                st.success(f"Utlåning registrerad på {borrower_name}!")
                st.balloons()
            else:
                st.error("Du måste ange ett namn på låntagaren för att kunna låna!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned_items = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    
    if loaned_items.empty:
        st.info("Inga instrument är utlånade just nu.")
    else:
        selected = st.selectbox("Välj instrument att återlämna:", 
                                loaned_items['Modell'] + " [" + loaned_items['Resurstagg'] + "] - " + loaned_items['Aktuell ägare'])
        
        if st.button("📥 Registrera återlämning"):
            tag = selected.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, 'Status'] = 'Tillgänglig'
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, 'Aktuell ägare'] = ""
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, 'Utlåningsdatum'] = ""
            save_data(st.session_state.df)
            st.success("Instrumentet är nu tillgängligt igen!")
            st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System & Export")
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    st.download_button("📂 Ladda ner inventarielista (CSV)", csv, "inventarie.csv", "text/csv")
