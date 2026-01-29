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

# --- HJÄLPFUNKTION: BILD TILL TEXT ---
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
    
    # REDIGERINGSLÄGE
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        # Kontrollera att indexet fortfarande finns kvar
        if idx < len(st.session_state.df):
            item = st.session_state.df.iloc[idx]
            with st.expander(f"Redigerar: {item['Modell']}", expanded=True):
                with st.form("edit_form"):
                    n_modell = st.text_input("Modell", value=item['Modell'])
                    n_status = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                    n_owner = st.text_input("Ägare", value=item['Aktuell ägare'])
                    
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Spara ändringar"):
                        st.session_state.df.at[idx, 'Modell'] = n_modell
                        st.session_state.df.at[idx, 'Status'] = n_status
                        st.session_state.df.at[idx, 'Aktuell ägare'] = n_owner
                        if save_data(st.session_state.df):
                            st.success("Ändringar sparade!")
                            st.session_state.editing_item = None
                            st.rerun()
                    
                    if c2.form_submit_button("Avbryt"):
                        st.session_state.editing_item = None
                        st.rerun()
                
                st.divider()
                # RADERA PRODUKT - Sektion
                st.warning("Farlig zon")
                if not st.session_state.delete_confirm:
                    if st.button("🗑️ Radera denna produkt"):
                        st.session_state.delete_confirm = True
                        st.rerun()
                else:
                    st.error(f"Är du säker på att du vill radera {item['Modell']} permanent?")
                    col_del1, col_del2 = st.columns(2)
                    if col_del1.button("JA, RADERA"):
                        st.session_state.df = st.session_state.df.drop(st.session_state.df.index[idx]).reset_index(drop=True)
                        if save_data(st.session_state.df):
                            st.session_state.editing_item = None
                            st.session_state.delete_confirm = False
                            st.success("Produkten raderad.")
                            st.rerun()
                    if col_del2.button("NEJ, ÅNGRA"):
                        st.session_state.delete_confirm = False
                        st.rerun()

    # SÖKLISTA
    search_query = st.text_input("Sök...", placeholder="Modell, ID...")
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
    results = st.session_state.df[mask]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1.2])
            with c1:
                foto = str(row['Enhetsfoto'])
                if foto.startswith("data:image"):
                    try:
                        st.image(foto, width=100)
                    except:
                        st.write("⚠️ Bildfel")
                else:
                    st.write("📷")
            with c2:
                st.markdown(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"{row['Modell']} tillagd!")
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.session_state.delete_confirm = False
                    st.rerun()

    # SIDEBAR CHECKOUT
    if st.session_state.cart:
        st.sidebar.divider()
        st.sidebar.subheader("🛒 Utcheckning")
        borrower = st.sidebar.text_input("Vem lånar?")
        if st.sidebar.button("Bekräfta utlån", type="primary"):
            if borrower:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                            ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, datetime.now().strftime("%Y-%m-%d")]
                if save_data(st.session_state.df):
                    st.balloons()
                    st.session_state.cart = []
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    with st.form("reg_form", clear_on_submit=True):
        m = st.text_input("Modell *")
        s = st.text_input("Serienummer *")
        t = st.text_input("Tillverkare")
        img = st.camera_input("Ta ett foto")
        
        if st.form_submit_button("Skapa Produkt"):
            if m and s:
                img_b64 = process_image_to_base64(img) if img else ""
                tag_id = str(random.randint(1000, 9999))
                new_row = {
                    "Enhetsfoto": img_b64, "Modell": m, "Serienummer": s, 
                    "Tillverkare": t, "Resurstagg": tag_id, "Status": "Tillgänglig",
                    "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.balloons()
                    st.success(f"Klar! Skapade {m} med ID {tag_id}")
            else:
                st.error("Modell och Serienummer krävs!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.multiselect("Välj instrument:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
        if st.button("Markera som återlämnade"):
            for s in selected:
                tag = s.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if save_data(st.session_state.df):
                st.success("Systemet uppdaterat!")
                st.rerun()
    else:
        st.info("Inga instrument är utlånade just nu.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.header("Admin & Logg")
    if st.button("Ladda om allt från Sheets"):
        st.session_state.df = load_data()
        st.rerun()
    
    st.subheader("Rådata (exkl. bilder)")
    st.dataframe(st.session_state.df.drop(columns=['Enhetsfoto'], errors='ignore'))
    
    with st.expander("Systemlogg"):
        st.code("\n".join(st.session_state.error_log))
