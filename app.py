import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
import os

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="InstrumentDB", layout="wide")
DB_FILE = "Musikinventarie.csv"

# CSS för att matcha dina bilder
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { background-color: #10b981; color: white; border-radius: 8px; border: none; }
    .stat-card { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- DATA-HANTERING ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare"]
    return pd.DataFrame(columns=cols)

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Initiera
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
    st.write("**Användare:** Senior Admin")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    # Statistik
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat-card'>Totalt antal<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök...")
    
    # Tabell
    st.write("---")
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    filtered_df = st.session_state.df[mask]
    
    if not filtered_df.empty:
        for idx, row in filtered_df.iterrows():
            r1, r2, r3, r4, r5 = st.columns([2, 1, 1, 1, 1])
            r1.write(f"**{row['Modell']}**\n\n{row['Tillverkare']}")
            
            qr_img = get_qr_image(row['Resurstagg'])
            buf = BytesIO()
            qr_img.save(buf, format="PNG")
            r2.image(buf, width=50)
            
            r3.write(row['Status'])
            r4.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
            
            if row['Status'] == 'Tillgänglig':
                if r5.button("➕ Låna", key=f"ln_{idx}"):
                    st.session_state.cart.append(row.to_dict())
                    st.rerun()
    else:
        st.info("Inga instrument matchar sökningen.")

# --- VY: LÄGG TILL (MED KAMERA) ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Lägg till musikutrustning")
    
    with st.form("add_form"):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillverkare = col2.text_input("Tillverkare")
        tagg = col1.text_input("Resurstagg (ID) *")
        sn = col2.text_input("Serienummer")
        
        st.write("---")
        st.subheader("Foto")
        cam_image = st.camera_input("Ta en bild på instrumentet")
        
        if st.form_submit_button("💾 Spara musikutrustning"):
            if modell and tagg:
                new_data = {
                    "Modell": modell,
                    "Tillverkare": tillverkare,
                    "Resurstagg": tagg,
                    "Serienummer": sn,
                    "Status": "Tillgänglig",
                    "Aktuell ägare": "",
                    "Enhetsfoto": "Kamerabild" if cam_image else ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("✅ Klart!")
            else:
                st.error("Fyll i Modell och Resurstagg!")

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System & Export")
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    st.download_button("📂 Ladda ner hela inventarielistan (CSV)", csv, "inventarie.csv", "text/csv")
    
    st.write("---")
    st.subheader("QR för utskrift")
    target = st.selectbox("Välj objekt:", st.session_state.df['Modell'] + " (" + st.session_state.df['Resurstagg'] + ")")
    if target:
        tag = target.split("(")[1].replace(")", "")
        qr_img = get_qr_image(tag)
        st.image(qr_img, width=200)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        st.download_button("📥 Ladda ner QR-bild (3x4 cm)", buf.getvalue(), f"QR_{tag}.png", "image/png")

# (Övriga menyer som Lånekorg och Återlämning läggs till på samma sätt med elif)
else:
    st.title(menu)
    st.info("Denna vy är under uppbyggnad, men sök- och lägg till-funktionerna fungerar!")
