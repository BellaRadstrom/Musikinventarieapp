import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
import os

# --- KONFIGURATION ---
st.set_page_config(page_title="InstrumentDB", layout="wide")
DB_FILE = "Musikinventarie.csv"

# CSS för att matcha din snygga design (Mörkt sidofält och vita kort)
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    .stat-card { background-color: white; padding: 20px; border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA FUNKTIONER ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=["Resurstagg", "Status", "Tillverkare", "Modell", "Resurstyp", "Aktuell ägare", "Serienummer"])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Initiera data
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY (Design matchad mot bild) ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    st.divider()
    menu = st.radio("MENY", 
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "⚙️ System & Export"],
        label_visibility="collapsed")
    st.spacer = st.container()
    st.write("---")
    st.caption("🟢 System Status: Säker anslutning")

# --- VY: SÖK & INVENTARIE (Matchad layout) ---
if menu == "🔍 Sök & Inventarie":
    col_title, col_exp = st.columns([4, 1])
    col_title.title("Sök & Inventarie")
    
    # Exportera CSV Knapp
    csv_data = st.session_state.df.to_csv(index=False).encode('utf-8')
    col_exp.download_button("📤 Exportera CSV", csv_data, "inventarie.csv", "text/csv")

    # Statistik-kort
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='stat-card'>Totalt antal<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='stat-card'>Tillgängliga<br><h2 style='color:green;'>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='stat-card'>Utlånade<br><h2 style='color:orange;'>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    st.write("")
    search = st.text_input("🔍 Sök på serienummer, modell, tillverkare eller tagg...", placeholder="Sök...")

    # Tabell-header
    st.write("---")
    h1, h2, h3, h4, h5 = st.columns([1, 2, 1, 1, 1])
    h1.write("**INSTRUMENT**")
    h2.write("**QR / TAGG**")
    h3.write("**STATUS**")
    h4.write("**AKTUELL ÄGARE**")
    h5.write("**ÅTGÄRD**")

    # Filtrera data
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    for idx, row in st.session_state.df[mask].iterrows():
        r1, r2, r3, r4, r5 = st.columns([1, 2, 1, 1, 1])
        
        # Instrument info
        r1.write(f"**{row['Modell']}**")
        r1.caption(f"{row['Tillverkare']} • {row['Resurstyp']}")
        
        # QR & Tagg (Genererar QR i realtid)
        qr_img = get_qr_image(row['Resurstagg'])
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        r2.image(buf, width=60)
        r2.caption(f"{row['Resurstagg']}")
        
        # Status
        status_color = "green" if row['Status'] == 'Tillgänglig' else "red"
        r3.markdown(f"<span style='color:{status_color};'>{row['Status']}</span>", unsafe_allow_html=True)
        
        # Ägare
        r4.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
        
        # Åtgärd
        if row['Status'] == 'Tillgänglig':
            if r5.button("➕ Låna", key=f"btn_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast(f"{row['Modell']} tillagd i korg")

# --- VY: SYSTEM & EXPORT (För QR-utskrift) ---
elif menu == "⚙️ System & Export":
    st.title("System & Export")
    st.subheader("Generera QR-kod för utskrift (3x4 cm)")
    
    target = st.selectbox("Välj instrument för utskrift:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'] + "]")
    if target:
        tag = target.split("[")[1].replace("]", "")
        final_qr = get_qr_image(tag)
        
        # Visa för användaren
        st.image(final_qr, width=200, caption=f"QR-kod för {tag}")
        
        # Download-knapp för exakt storlek
        buf = BytesIO()
        final_qr.save(buf, format="PNG")
        st.download_button(f"📥 Ladda ner QR för {tag} (PNG)", buf.getvalue(), f"QR_{tag}.png", "image/png")
        st.info("Tips: När du skriver ut bilden, ställ in din skrivare på '3x4 cm' för att matcha dina etiketter.")

# (Resten av logiken för Lägg till, Korg och Retur behålls från förra versionen...)
