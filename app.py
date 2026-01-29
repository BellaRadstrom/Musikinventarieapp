import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image

# --- CONFIG ---
st.set_page_config(page_title="Musik-Inventering Pro", layout="wide", page_icon="🎸")

# --- CSS FÖR KNAPPAR OCH LAYOUT ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .stExpander { border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- ANSLUTNING & DATA ---
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_connection()

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        return data.fillna("")
    except:
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        df_to_save = df.fillna("").astype(str)
        conn.update(worksheet="Sheet1", data=df_to_save)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Skrivfel: {e}")
        return False

# Session States
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- HJÄLPFUNKTIONER ---
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
    st.header("Sök i inventariet")
    
    col_search, col_scan = st.columns([3, 1])
    search_query = col_search.text_input("Sök i alla kolumner...", placeholder="Modell, ID, Färg...")
    
    # QR-Scanner (Simulering via kamera-input eller text)
    if col_scan.button("📷 Skanna QR"):
        st.info("Använd sökfältet med din QR-scanner/kamera.")

    df = st.session_state.df
    if not df.empty:
        # Global sökning
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        results = df[mask]

        for idx, row in results.iterrows():
            with st.expander(f"{row['Modell']} ({row['Tillverkare']}) - {row['Status']}"):
                c1, c2, c3 = st.columns([1, 2, 1])
                
                with c1:
                    # Visa QR-kod för utskrift
                    qr_img = generate_qr(row['Resurstagg'])
                    st.image(qr_img, caption="QR-ID", width=100)
                    st.download_button("Hämta QR (3x4cm)", qr_img, file_name=f"QR_{row['Resurstagg']}.png", mime="image/png")
                
                with c2:
                    # Editering
                    with st.popover("Redigera info"):
                        new_model = st.text_input("Modell", value=row['Modell'], key=f"mod_{idx}")
                        if st.button("Spara ändring", key=f"save_ed_{idx}"):
                            st.session_state.df.at[idx, 'Modell'] = new_model
                            save_data(st.session_state.df)
                            st.rerun()
                    st.write(f"**ID:** {row['Resurstagg']} | **SN:** {row['Serienummer']}")
                
                with c3:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("➕ Till lånekorg", key=f"add_{idx}"):
                            if row['Resurstagg'] not in [i['Resurstagg'] for i in st.session_state.cart]:
                                st.session_state.cart.append(row.to_dict())
                                st.toast("Tillagd!")
                    else:
                        st.warning(f"Lånad av: {row['Aktuell ägare']}")

    # LÅNEKORG (Flytande sektion)
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
            else:
                st.sidebar.error("Namn krävs!")

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
        tag = col2.text_input("Resurstagg (ID)", help="Lämna tom för att generera automatiskt")
        
        uploaded_img = st.file_uploader("Ladda upp bild", type=['jpg', 'png'])
        cam_img = st.camera_input("Ta foto")
        
        if st.form_submit_button("Registrera"):
            if modell and sn:
                res_id = tag if tag else str(random.randint(100000, 999999))
                new_row = {
                    "Enhetsfoto": "Ja" if (uploaded_img or cam_img) else "Nej",
                    "Modell": modell, "Tillverkare": tillverkare, "Typ": typ,
                    "Färg": färg, "Resurstagg": res_id, "Streckkod": res_id,
                    "Serienummer": sn, "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"Objekt {res_id} registrerat!")
            else:
                st.error("Modell och Serienummer är tvingande!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    
    if not loaned.empty:
        selected_items = st.multiselect("Välj instrument som lämnas tillbaka:", 
                                        loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}] - {r['Aktuell ägare']}", axis=1))
        
        if st.button("Markera som återlämnade", type="primary"):
            for item in selected_items:
                tag = item.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
            if save_data(st.session_state.df):
                st.success("Produkter återförda i lager!")
                st.rerun()
    else:
        st.info("Inga produkter är för närvarande utlånade.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.header("Administration")
    
    c1, c2 = st.columns(2)
    # Exportfunktioner
    csv_all = st.session_state.df.to_csv(index=False).encode('utf-8')
    c1.download_button("📥 Exportera Lagersaldo (CSV)", csv_all, "lagersaldo.csv", "text/csv")
    
    loaned_df = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    csv_loaned = loaned_df.to_csv(index=False).encode('utf-8')
    c2.download_button("📥 Exportera Utlåningslista (CSV)", csv_loaned, "utlaning.csv", "text/csv")
    
    st.divider()
    st.write("Rådata från Sheets:")
    st.dataframe(st.session_state.df)

# --- VY: INVENTERING ---
elif menu == "📋 Inventering":
    st.header("Årsinventering")
    if 'inv_list' not in st.session_state:
        st.session_state.inv_list = []
    
    inv_scan = st.text_input("Skanna/Sök produkt att lägga till i inventeringslistan")
    if inv_scan:
        match = st.session_state.df[st.session_state.df['Resurstagg'] == inv_scan]
        if not match.empty:
            if inv_scan not in [i['Resurstagg'] for i in st.session_state.inv_list]:
                st.session_state.inv_list.append(match.iloc[0].to_dict())
                st.success(f"{match.iloc[0]['Modell']} tillagd!")
    
    st.write(f"Antal inventerade objekt: {len(st.session_state.inv_list)}")
    st.table(pd.DataFrame(st.session_state.inv_list)[['Modell', 'Resurstagg', 'Status']] if st.session_state.inv_list else pd.DataFrame())
    
    if st.button("Spara inventeringsfil"):
        # Här kan vi spara till en ny flik eller CSV
        inv_df = pd.DataFrame(st.session_state.inv_list)
        st.download_button("Ladda ner inventeringsfil", inv_df.to_csv(index=False), "inventering_2024.csv")
