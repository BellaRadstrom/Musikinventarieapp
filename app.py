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

# --- HJÄLPFUNKTION: BILD TILL TEXT (BASE64) ---
def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        # Ändra storlek för att inte spräcka Sheets cell-gräns (max 50k tecken)
        img.thumbnail((300, 300))
        
        buffered = BytesIO()
        # Spara som JPEG med lite komprimering
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=70)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        add_log(f"BILD-KONVERTERINGSFEL: {str(e)}")
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
        add_log(f"Läsfel Sheets: {str(e)}")
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        df_to_save = df.fillna("").astype(str)
        conn.update(worksheet="Sheet1", data=df_to_save)
        st.cache_data.clear()
        add_log("System: Lyckades spara till Google Sheets.")
        return True
    except Exception as e:
        add_log(f"Skrivfel Sheets: {str(e)}")
        st.error("Kunde inte spara till Sheets. Bilden kan vara för stor eller kolumnnamn saknas.")
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
    search_query = st.text_input("Sök i inventariet...", placeholder="Sök på vad som helst...")
    
    df = st.session_state.df
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        results = df[mask]

        for idx, row in results.iterrows():
            with st.container(border=True):
                col_img, col_info, col_action = st.columns([1, 3, 1])
                with col_img:
                    # Visar Base64-bilden direkt
                    if row['Enhetsfoto'] and str(row['Enhetsfoto']).startswith("data:image"):
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
                        st.download_button("Hämta", qr_img, file_name=f"QR_{row['Resurstagg']}.png", key=f"dl_{idx}")
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Lägg till", key=f"add_{idx}"):
                            if row['Resurstagg'] not in [i['Resurstagg'] for i in st.session_state.cart]:
                                st.session_state.cart.append(row.to_dict())
                                st.toast(f"{row['Modell']} i korgen!")

    if st.session_state.cart:
        st.sidebar.divider()
        st.sidebar.subheader("🛒 Lånekorg")
        for item in st.session_state.cart:
            st.sidebar.caption(f"• {item['Modell']}")
        borrower = st.sidebar.text_input("Vem lånar?")
        if st.sidebar.button("Bekräfta lån"):
            if borrower:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                            ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = \
                                            ['Utlånad', borrower, datetime.now().strftime("%Y-%m-%d")]
                if save_data(st.session_state.df):
                    st.session_state.cart = []
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny registrering")
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        modell = c1.text_input("Modell *")
        sn = c2.text_input("Serienummer *")
        tillverkare = c1.text_input("Tillverkare")
        typ = c2.selectbox("Typ", ["Gitarr", "Bas", "Trummor", "Keyboard", "PA", "Kabel", "Övrigt"])
        färg = c1.text_input("Färg")
        tag = c2.text_input("Resurstagg (ID)")
        
        up_img = st.file_uploader("Välj bild", type=['jpg', 'png'])
        cam_img = st.camera_input("Ta foto med kamera")
        
        submit = st.form_submit_button("Spara till systemet")
        
        if submit:
            if modell and sn:
                res_id = tag if tag else str(random.randint(100000, 999999))
                
                # Bildhantering
                image_data = ""
                active_img = cam_img if cam_img else up_img
                if active_img:
                    image_data = process_image_to_base64(active_img)
                
                new_row = {
                    "Enhetsfoto": image_data,
                    "Modell": modell, 
                    "Tillverkare": tillverkare, 
                    "Typ": typ,
                    "Färg": färg, 
                    "Resurstagg": res_id, 
                    "Streckkod": res_id,
                    "Serienummer": sn, 
                    "Status": "Tillgänglig", 
                    "Aktuell ägare": "", 
                    "Utlåningsdatum": ""
                }
                
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"Objekt {modell} registrerat!")
                    st.rerun()
            else:
                st.error("Modell och Serienummer är obligatoriska!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.multiselect("Välj objekt att återlämna:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
        if st.button("Markera som återlämnade"):
            for s in selected:
                t = s.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == t, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
            if save_data(st.session_state.df):
                st.success("Uppdaterat!")
                st.rerun()
    else:
        st.info("Inga utlånade objekt hittades.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.header("Administration")
    
    with st.expander("Systemlogg"):
        if st.session_state.error_log:
            st.code("\n".join(st.session_state.error_log))
            if st.button("Rensa logg"):
                st.session_state.error_log = []
                st.rerun()
        else:
            st.write("Inga händelser loggade.")

    st.divider()
    # Visa tabellen men dölj den tunga bild-kolumnen för bättre prestanda i admin
    df_preview = st.session_state.df.copy()
    if "Enhetsfoto" in df_preview.columns:
        df_preview["Enhetsfoto"] = df_preview["Enhetsfoto"].apply(lambda x: "✅ Bild finns" if x and len(str(x)) > 100 else "❌ Ingen bild")
    st.dataframe(df_preview)
    
    if st.button("Tvinga omladdning från Sheets"):
        st.cache_resource.clear()
        st.session_state.df = load_data()
        st.rerun()

# --- VY: INVENTERING ---
elif menu == "📋 Inventering":
    st.header("Inventering")
    if 'inv_list' not in st.session_state: st.session_state.inv_list = []
    inv_scan = st.text_input("Skanna eller skriv ID")
    if inv_scan:
        match = st.session_state.df[st.session_state.df['Resurstagg'] == inv_scan]
        if not match.empty:
            if inv_scan not in [i['Resurstagg'] for i in st.session_state.inv_list]:
                st.session_state.inv_list.append(match.iloc[0].to_dict())
                st.success(f"{match.iloc[0]['Modell']} tillagd i inventeringslistan!")
    
    if st.session_state.inv_list:
        inv_df = pd.DataFrame(st.session_state.inv_list)
        st.table(inv_df[['Modell', 'Resurstagg', 'Status']])
        st.download_button("Exportera inventering (CSV)", inv_df.to_csv(index=False), "inventering.csv")
