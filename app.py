import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
import os
from datetime import datetime

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="InstrumentDB", layout="wide")
DB_FILE = "Musikinventarie.csv"

# CSS för att matcha dina bilder exakt (Mörkt sidofält, gröna knappar, kort-design)
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { background-color: #10b981; color: white; border-radius: 8px; border: none; width: 100%; }
    .stat-card { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .instrument-row { background-color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #f3f4f6; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA-HANTERING ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    # Skapar filen om den saknas med rätt kolumner från dina bilder
    cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare"]
    df = pd.DataFrame(columns=cols)
    df.to_csv(DB_FILE, index=False)
    return df

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
    st.write(f"**Användare:** Senior Admin")

# --- VY: SÖK & INVENTARIE (Matchar bild 3) ---
if menu == "🔍 Sök & Inventarie":
    col_t, col_btn = st.columns([4, 1])
    col_t.title("Sök & Inventarie")
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    col_btn.download_button("📂 Exportera CSV", csv, "inventarie.csv", "text/csv")

    # Statistik-kort
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat-card'>Totalt antal<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök på serienummer, modell, tillverkare eller tagg...")
    
    # Tabell-layout från bild 3
    st.write("---")
    h1, h2, h3, h4, h5 = st.columns([2, 1, 1, 1, 1])
    h1.caption("INSTRUMENT")
    h2.caption("QR / TAGG")
    h3.caption("STATUS")
    h4.caption("AKTUELL ÄGARE")
    h5.caption("ÅTGÄRD")

    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    for idx, row in st.session_state.df[mask].iterrows():
        r1, r2, r3, r4, r5 = st.columns([2, 1, 1, 1, 1])
        r1.write(f"**{row['Modell']}**")
        r1.caption(f"{row['Tillverkare']} • {row['Typ']}")
        
        # QR-kod
        qr_img = get_qr_image(row['Resurstagg'])
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        r2.image(buf, width=50)
        r2.caption(row['Resurstagg'])
        
        # Status-pilla
        st_color = "#dcfce7" if row['Status'] == 'Tillgänglig' else "#fee2e2"
        txt_color = "#166534" if row['Status'] == 'Tillgänglig' else "#991b1b"
        r3.markdown(f"<span style='background-color:{st_color}; color:{txt_color}; padding:4px 12px; border-radius:15px; font-size:12px;'>{row['Status']}</span>", unsafe_allow_html=True)
        
        r4.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
        
        if row['Status'] == 'Tillgänglig':
            if r5.button("➕ Låna", key=f"ln_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.rerun()

# --- VY: LÄGG TILL (Matchar bild 4) ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Lägg till musikutrustning")
    st.write("Fyll i informationen nedan för att registrera en ny produkt i systemet.")
    
    with st.container():
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *", placeholder="Ex. Stratocaster eller Mixerbord")
        tillverkare = col2.text_input("Tillverkare", placeholder="Ex. Fender eller Yamaha")
        typ = col1.text_input("Typ av utrustning", placeholder="Ex. Elgitarr eller Ljudkort")
        farg = col2.text_input("Färg / Utförande", placeholder="Ex. Sunburst eller Svart")
        
        col3, col4, col5 = st.columns(3)
        tagg = col3.text_input("Resurstagg (ID) *", placeholder="Ex. EQ-102")
        # QR lämnas tom för att generera automatiskt
        sn = col5.text_input("Serienummer", placeholder="Ex. SN-123456")
        
        foto_url = st.text_input("Foto (Bild-URL)", placeholder="Klistra in länk...")
        
        if st.button("💾 Spara musikutrustning"):
            if modell and tagg:
                new_data = {
                    "Enhetsfoto": foto_url,
                    "Modell": modell,
                    "Tillverkare": tillverkare,
                    "Typ": typ,
                    "Färg": farg,
                    "Resurstagg": tagg,
                    "Streckkod": tagg,
                    "Serienummer": sn,
                    "Status": "Tillgänglig",
                    "Aktuell ägare": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("✅ Produkten har lagts till!")
                st.balloons()
            else:
                st.error("Modell och Resurstagg är obligatoriska fält.")

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System & Export")
    st.subheader("Exportera QR-koder för etiketter (3x4 cm)")
    
    selected_qr = st.selectbox("Välj objekt:", st.session_state.df['Modell'] + " (" + st.session_state.df['Resurstagg'] + ")")
    if selected_qr:
        tag = selected_qr.split("(")[1].replace(")", "")
        img = get_qr_image(tag)
        st.image(img, width=200)
        
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.download_button(f"📥 Ladda ner QR ({tag})", buf.getvalue(), f"QR_{tag}.png", "image/png")
