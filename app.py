import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64

# --- CONFIG ---
st.set_page_config(page_title="Musik-Inventering Pro", layout="wide", page_icon="🎸")

# --- SESSION STATE ---
if 'error_log' not in st.session_state:
    st.session_state.error_log = []
if 'editing_item' not in st.session_state:
    st.session_state.editing_item = None
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'delete_confirm' not in st.session_state:
    st.session_state.delete_confirm = False

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {msg}")

# --- HJÄLPFUNKTIONER ---
def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((250, 250)) 
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=60)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except Exception as e:
        add_log(f"BILD-FEL: {str(e)}")
        return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- ANSLUTNING ---
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_connection()

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        return data.fillna("")
    except Exception as e:
        add_log(f"Läsfel: {str(e)}")
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.cache_data.clear()
        return True
    except Exception as e:
        add_log(f"Skrivfel: {str(e)}")
        st.error("Kunde inte spara till Sheets.")
        return False

# Ladda initial data
if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- SIDOMENY ---
st.sidebar.title("🎸 InstrumentDB")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # Kameraskanning för sökning
    with st.expander("📷 Skanna QR/Streckkod för att söka"):
        camera_search = st.camera_input("Rikta kameran mot koden")
        if camera_search:
            st.info("Sökning via kamera kräver en dedikerad QR-bibliotekssida, men du kan skriva in koden nedan tills vidare.")

    # Redigeringsläge (Högst upp om aktivt)
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        if idx < len(st.session_state.df):
            item = st.session_state.df.iloc[idx]
            with st.status(f"Redigerar nu: {item['Modell']}", expanded=True):
                with st.form("edit_form"):
                    col_e1, col_e2 = st.columns(2)
                    e_modell = col_e1.text_input("Modell", value=item['Modell'])
                    e_tillv = col_e2.text_input("Tillverkare", value=item['Tillverkare'])
                    e_status = col_e1.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Försvunnen"], index=0)
                    e_owner = col_e2.text_input("Ägare", value=item['Aktuell ägare'])
                    
                    if st.form_submit_button("Spara ändringar"):
                        st.session_state.df.at[idx, 'Modell'] = e_modell
                        st.session_state.df.at[idx, 'Tillverkare'] = e_tillv
                        st.session_state.df.at[idx, 'Status'] = e_status
                        st.session_state.df.at[idx, 'Aktuell ägare'] = e_owner
                        if save_data(st.session_state.df):
                            st.success("Uppdaterat!")
                            st.session_state.editing_item = None
                            st.rerun()
                
                if st.button("🗑️ Ta bort produkt permanent", type="secondary"):
                    st.session_state.delete_confirm = True
                
                if st.session_state.delete_confirm:
                    st.error("ÄR DU SÄKER?")
                    if st.button("JA - RADERA"):
                        st.session_state.df = st.session_state.df.drop(st.session_state.df.index[idx]).reset_index(drop=True)
                        save_data(st.session_state.df)
                        st.session_state.editing_item = None
                        st.session_state.delete_confirm = False
                        st.rerun()

    # Sökfält
    search_query = st.text_input("Sök på modell, märke eller ID...", placeholder="T.ex. Fender, 1234...")
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
    results = st.session_state.df[mask]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"):
                    st.image(row['Enhetsfoto'], width=100)
                else: st.write("📷")
            with c2:
                st.markdown(f"**{row['Modell']}**")
                st.caption(f"{row['Tillverkare']} | {row['Typ']}")
                st.caption(f"SN: {row['Serienummer']}")
            with c3:
                # Automatisk QR-visning
                qr_data = str(row['Resurstagg'])
                st.image(generate_qr(qr_data), caption=f"ID: {qr_data}", width=80)
            with c4:
                st.write(f"Status: {row['Status']}")
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Lagd i korg")
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

    # Sidebar Checkout
    if st.session_state.cart:
        st.sidebar.subheader("🛒 Din Lånekorg")
        borrower = st.sidebar.text_input("Låntagarens namn")
        if st.sidebar.button("Genomför lån"):
            if borrower:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                            ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, datetime.now().strftime("%Y-%m-%d")]
                save_data(st.session_state.df)
                st.balloons()
                st.session_state.cart = []
                st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt instrument")
    with st.form("full_reg", clear_on_submit=True):
        col1, col2 = st.columns(2)
        # Obligatoriska
        modell = col1.text_input("Modell *")
        sn = col2.text_input("Serienummer *")
        
        # Övriga fält från Sheets
        tillv = col1.text_input("Tillverkare")
        typ = col2.selectbox("Typ", ["Gitarr", "Bas", "Trummor", "Keyboard", "PA", "Kabel", "Övrigt"])
        färg = col1.text_input("Färg")
        tag = col2.text_input("Resurstagg / ID (Lämna tom för auto)")
        
        img = st.camera_input("Ta foto")
        
        if st.form_submit_button("Spara till Inventariet"):
            if modell and sn:
                res_id = tag if tag else str(random.randint(100000, 999999))
                img_b64 = process_image_to_base64(img) if img else ""
                
                new_row = {
                    "Enhetsfoto": img_b64, "Modell": modell, "Tillverkare": tillv,
                    "Typ": typ, "Färg": färg, "Resurstagg": res_id, 
                    "Streckkod": res_id, "Serienummer": sn, "Status": "Tillgänglig",
                    "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.balloons()
                    st.success(f"Registrerad! ID: {res_id}")
            else:
                st.error("Modell och Serienummer måste fyllas i!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        to_return = st.multiselect("Välj instrument att återlämna:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
        if st.button("Bekräfta återlämning"):
            for s in to_return:
                tid = s.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            save_data(st.session_state.df)
            st.rerun()

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.header("Administration")
    st.write("Fullständig databas (utan bilder):")
    st.dataframe(st.session_state.df.drop(columns=['Enhetsfoto'], errors='ignore'))
    if st.button("Tvinga omladdning från Sheets"):
        st.session_state.df = load_data()
        st.rerun()
