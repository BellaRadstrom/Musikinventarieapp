import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
import os

# --- KONFIGURATION ---
st.set_page_config(page_title="Musikinventarie System", layout="wide")
DB_FILE = "Musikinventarie.csv"

# --- FUNKTIONER FÖR DATA ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    else:
        # Skapa tom DF med dina kolumner om filen saknas
        cols = ["Enhetsfoto", "Resurstagg", "Status", "Tillverkare", "Modell", "Resurstyp", "Färg", "Serienummer", "Inköpsdatum", "Inköpspris", "Aktuell ägare", "Streckkod"]
        return pd.DataFrame(columns=cols)

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# Initiera data i sessionen
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- QR-KODSGENERERING ---
def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# --- NAVIGATION ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Inventarie", "➕ Lägg till ny", "🛒 Varukorg", "🔄 Returnera", "📊 Export"])

# --- VY 1: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("🎸 Musikinstrument & Inventarie")
    search = st.text_input("Sök i hela registret...")
    
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    df_to_show = st.session_state.df[mask]

    for idx, row in df_to_show.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                if pd.notnull(row['Enhetsfoto']):
                    st.image(row['Enhetsfoto'], width=100)
            with col2:
                st.write(f"**{row['Modell']}** ({row['Tillverkare']})")
                st.caption(f"Tagg: {row['Resurstagg']} | Status: {row['Status']}")
            with col3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("Lägg i korg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"{row['Modell']} tillagd!")
            st.divider()

# --- VY 2: LÄGG TILL NY (MED KAMERA) ---
elif menu == "➕ Lägg till ny":
    st.title("Registrera nytt instrument")
    with st.form("new_item"):
        col1, col2 = st.columns(2)
        resurstagg = col1.text_input("Resurstagg (t.ex. GIT-001)")
        modell = col2.text_input("Modell/Namn")
        typ = col1.selectbox("Typ", ["Gitarr", "Keyboard", "Förstärkare", "Annat"])
        pris = col2.number_input("Inköpspris", min_value=0)
        
        # Kamera/Uppladdning
        img_file = st.camera_input("Ta ett foto på objektet")
        
        if st.form_submit_button("Spara objekt"):
            new_id = resurstagg if resurstagg else str(len(st.session_state.df) + 1)
            new_row = {
                "Resurstagg": new_id,
                "Modell": modell,
                "Status": "Tillgänglig",
                "Resurstyp": typ,
                "Inköpspris": pris,
                "Streckkod": new_id, # QR baseras på tagg
                "Enhetsfoto": "img_placeholder.png" # Här krävs lagring för riktiga bilder
            }
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(st.session_state.df)
            st.success("Objekt sparat!")

# --- VY 3: VARUKORG ---
elif menu == "🛒 Varukorg":
    st.title("Utlåning")
    if not st.session_state.cart:
        st.info("Korgen är tom")
    else:
        borrower = st.text_input("Vem lånar?")
        for item in st.session_state.cart:
            st.write(f"• {item['Modell']} ({item['Resurstagg']})")
        
        if st.button("Bekräfta utlån"):
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 'Status'] = 'Utlånad'
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 'Aktuell ägare'] = borrower
            save_data(st.session_state.df)
            st.session_state.cart = []
            st.success("Utlånat!")

# --- VY 4: RETURNERA ---
elif menu == "🔄 Returnera":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    selected = st.selectbox("Välj objekt att returnera", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
    if st.button("Returnera till lager"):
        tag = selected.split("[")[1].split("]")[0]
        st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, 'Status'] = 'Tillgänglig'
        st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, 'Aktuell ägare'] = ""
        save_data(st.session_state.df)
        st.rerun()

# --- VY 5: EXPORT & QR ---
elif menu == "📊 Export":
    st.title("Exportera & QR-koder")
    
    # Export CSV
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    st.download_button("Ladda ner Inventarielista (CSV)", csv, "inventarie.csv", "text/csv")
    
    st.divider()
    st.subheader("Generera QR för utskrift (3x4 cm)")
    item_to_qr = st.selectbox("Välj objekt för QR", st.session_state.df['Modell'] + " (" + st.session_state.df['Resurstagg'] + ")")
    
    if item_to_qr:
        tag = item_to_qr.split("(")[1].replace(")", "")
        qr_img = generate_qr(tag)
        
        # Skala om till "3x4 cm" proportioner (ca 300x400 pixlar för skärm/utskrift)
        qr_print = qr_img.resize((300, 300))
        st.image(qr_print, caption=f"QR för {tag}")
        
        # Download knapp för bild
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        st.download_button("Ladda ner QR-bild", buf.getvalue(), f"QR_{tag}.png", "image/png")