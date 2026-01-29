import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import traceback

# Google Drive API Importer
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

# --- CONFIG ---
st.set_page_config(page_title="Musik-Inventering Pro", layout="wide", page_icon="🎸")

# --- DRIVE KONFIGURATION ---
FOLDER_ID = "1KDIg6_7MmOrRRwA1MwLiePVAwbqG60aR"

# --- SESSION STATE FÖR LOGG ---
if 'error_log' not in st.session_state:
    st.session_state.error_log = []

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {msg}")

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .stExpander { border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- HJÄLPFUNKTION: DRIVE UPPLADDNING ---
def upload_to_drive(file_content, filename):
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        # Vi lägger till 'delegated_user' om det vore Workspace, men för privat:
        drive_service = build('drive', 'v3', credentials=credentials)

        # Vi skapar filen utan 'parents' först för att se om den accepterar det,
        # eller så använder vi 'fields' för att tvinga fram rätt ID.
        file_metadata = {
            'name': filename,
            'parents': [FOLDER_ID]
        }
        
        media = MediaIoBaseUpload(BytesIO(file_content), mimetype='image/jpeg', resumable=True)
        
        # Vi provar att använda 'resumable=True' vilket ibland hanterar kvota bättre
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        file_id = file.get('id')
        
        # Sätt rättigheter
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'},
            supportsAllDrives=True
        ).execute()
        
        return f"https://drive.google.com/uc?export=view&id={file_id}"
    except Exception as e:
        # Om det fortfarande skiter sig, logga exakt vad Google svarar
        add_log(f"DRIVE-FEL: {str(e)}")
        return ""

# --- ANSLUTNING & DATA ---
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
        df_to_save = df.fillna("").astype(str)
        conn.update(worksheet="Sheet1", data=df_to_save)
        st.cache_data.clear()
        add_log("System: Lyckades spara till Sheets.")
        return True
    except Exception as e:
        add_log(f"SKRIVFEL Sheets: {str(e)}")
        st.error(f"Skrivfel: {e}")
        return False

# Initiera State
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- HJÄLPFUNKTION: QR-KOD ---
def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- SIDOMENY ---
st.sidebar.title("🎸 InstrumentDB")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "📋 Inventering", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    search_query = st.text_input("Sök i inventariet...", placeholder="Skriv modell, märke, ID eller färg...")
    
    df = st.session_state.df
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        results = df[mask]

        for idx, row in results.iterrows():
            with st.container(border=True):
                col_img, col_info, col_action = st.columns([1, 3, 1])
                with col_img:
                    if row['Enhetsfoto'] and str(row['Enhetsfoto']).startswith("http"):
                        st.image(row['Enhetsfoto'], width=120)
                    else:
                        st.markdown("📷\n*Ingen bild*")
                with col_info:
                    st.markdown(f"### {row['Modell']}")
                    st.caption(f"{row['Tillverkare']} | ID: {row['Resurstagg']} | SN: {row['Serienummer']}")
                    if row['Status'] == 'Tillgänglig':
                        st.success(f"✅ {row['Status']}")
                    else:
                        st.error(f"🔴 Utlånad till: {row['Aktuell ägare']}")
                with col_action:
                    with st.popover("QR"):
                        qr_img = generate_qr(row['Resurstagg'])
                        st.image(qr_img, use_container_width=True)
                        st.download_button("Ladda ner", qr_img, file_name=f"QR_{row['Resurstagg']}.png", key=f"dl_{idx}")
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Lägg till", key=f"add_{idx}"):
                            if row['Resurstagg'] not in [i['Resurstagg'] for i in st.session_state.cart]:
                                st.session_state.cart.append(row.to_dict())
                                st.toast(f"{row['Modell']} i korgen!")

    if st.session_state.cart:
        st.sidebar.divider()
        st.sidebar.subheader("🛒 Lånekorg")
        for i, item in enumerate(st.session_state.cart):
            st.sidebar.caption(f"{item['Modell']} ({item['Resurstagg']})")
        borrower_name = st.sidebar.text_input("Låntagarens namn")
        if st.sidebar.button("Slutför Lån", type="primary"):
            if borrower_name:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                            ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = \
                                            ['Utlånad', borrower_name, datetime.now().strftime("%Y-%m-%d")]
                if save_data(st.session_state.df):
                    st.session_state.cart = []
                    st.success("Lån registrerat!")
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt objekt")
    with st.form("reg_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        sn = col2.text_input("Serienummer *")
        tillverkare = col1.text_input("Tillverkare")
        typ = col2.selectbox("Typ", ["Gitarr", "Bas", "Trummor", "Keyboard", "PA", "Kabel", "Övrigt"])
        färg = col1.text_input("Färg")
        tag = col2.text_input("Resurstagg (ID)")
        
        uploaded_img = st.file_uploader("Ladda upp bild", type=['jpg', 'png'])
        cam_img = st.camera_input("Ta foto")
        
        if st.form_submit_button("Registrera"):
            if modell and sn:
                res_id = tag if tag else str(random.randint(100000, 999999))
                image_url = ""
                active_img = cam_img if cam_img else uploaded_img
                if active_img:
                    with st.spinner("Laddar upp till Drive..."):
                        image_url = upload_to_drive(active_img.getvalue(), f"{res_id}.jpg")
                
                new_row = {
                    "Enhetsfoto": image_url, "Modell": modell, "Tillverkare": tillverkare, "Typ": typ,
                    "Färg": färg, "Resurstagg": res_id, "Streckkod": res_id,
                    "Serienummer": sn, "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"Objekt {res_id} registrerat!")
            else:
                st.error("Modell och Serienummer krävs!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected_items = st.multiselect("Välj instrument:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
        if st.button("Markera som återlämnade"):
            for item in selected_items:
                tag = item.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
            if save_data(st.session_state.df):
                st.rerun()

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.header("Administration & Logg")
    
    st.subheader("Systemlogg (Felsökning)")
    if st.session_state.error_log:
        st.code("\n".join(st.session_state.error_log))
        if st.button("Rensa logg"):
            st.session_state.error_log = []
            st.rerun()
    else:
        st.info("Inga fel registrerade.")

    st.divider()
    c1, c2 = st.columns(2)
    csv_all = st.session_state.df.to_csv(index=False).encode('utf-8')
    c1.download_button("📥 Exportera Lagersaldo", csv_all, "lagersaldo.csv", "text/csv")
    
    if st.button("Tvinga omladdning från Sheets"):
        st.cache_resource.clear()
        st.session_state.df = load_data()
        st.rerun()
    
    st.dataframe(st.session_state.df)

# --- VY: INVENTERING ---
elif menu == "📋 Inventering":
    st.header("Inventering")
    if 'inv_list' not in st.session_state: st.session_state.inv_list = []
    inv_scan = st.text_input("Skanna/Sök ID")
    if inv_scan:
        match = st.session_state.df[st.session_state.df['Resurstagg'] == inv_scan]
        if not match.empty and inv_scan not in [i['Resurstagg'] for i in st.session_state.inv_list]:
            st.session_state.inv_list.append(match.iloc[0].to_dict())
            st.success("Tillagd!")
    st.write(f"Antal: {len(st.session_state.inv_list)}")
    if st.session_state.inv_list:
        st.table(pd.DataFrame(st.session_state.inv_list)[['Modell', 'Resurstagg']])
        if st.button("Exportera Inventeringslista"):
            st.download_button("Ladda ner CSV", pd.DataFrame(st.session_state.inv_list).to_csv(index=False), "inv.csv")

