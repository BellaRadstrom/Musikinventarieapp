import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- CONFIG ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# --- ANSLUTNING ---
@st.cache_resource
def get_connection():
    # Streamlit läser automatiskt från [connections.gsheets] i secrets
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_connection()

def load_data():
    try:
        # ttl=0 gör att vi inte cachar gammal data när vi sparar nytt
        return conn.read(worksheet="Sheet1", ttl=0)
    except Exception as e:
        st.error(f"Kunde inte hämta data: {e}")
        return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear() # Tvinga omladdning
        return True
    except Exception as e:
        st.error(f"Fel vid sparande: {e}")
        return False

# Session State
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- UI ---
st.sidebar.title("🎵 Musikinventering")
menu = st.sidebar.radio("MENY", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# --- SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.title("Sök Instrument")
    
    col1, col2 = st.columns([3, 1])
    search = col1.text_input("Sök på modell, märke eller ID...")
    if col2.button("🔄 Uppdatera"):
        st.session_state.df = load_data()
        st.rerun()

    df = st.session_state.df
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        results = df[mask]

        for idx, row in results.iterrows():
            with st.expander(f"{row['Modell']} - {row['Status']}"):
                st.write(f"**Märke:** {row['Tillverkare']} | **ID:** {row['Resurstagg']}")
                if row['Status'] == 'Utlånad':
                    st.warning(f"Lånad av: {row['Låntagare']}")
                else:
                    if st.button("Lägg i lånekorg", key=f"add_{row['Resurstagg']}"):
                        if not any(item['Resurstagg'] == row['Resurstagg'] for item in st.session_state.cart):
                            st.session_state.cart.append(row.to_dict())
                            st.toast("Tillagd!")

    if st.session_state.cart:
        st.divider()
        st.subheader("🛒 Din lånekorg")
        for item in st.session_state.cart:
            st.write(f"• {item['Modell']} ({item['Resurstagg']})")
        
        borrower = st.text_input("Vem lånar?")
        if st.button("BEKRÄFTA LÅN", type="primary") and borrower:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', borrower]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.success("Lån registrerat!")
                st.rerun()

# --- REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.title("Registrera ny utrustning")
    with st.form("add_form"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("Resurstagg (valfritt)")
        img = st.camera_input("Ta bild")
        
        if st.form_submit_button("Spara"):
            if m:
                new_tag = tag if tag else str(random.randint(1000, 9999))
                new_row = pd.DataFrame([{"Modell": m, "Tillverkare": t, "Resurstagg": new_tag, "Status": "Tillgänglig", "Låntagare": ""}])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"{m} tillagd i listan!")
            else:
                st.error("Modellnamn krävs.")

# --- ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        item_to_return = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Markera som återlämnad"):
            tag = item_to_return.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Låntagare']] = ['Tillgänglig', '']
            if save_data(st.session_state.df):
                st.rerun()
    else:
        st.info("Inga lånade föremål just nu.")

# --- ADMIN ---
elif menu == "⚙️ Admin":
    st.title("Admin-översikt")
    st.dataframe(st.session_state.df, use_container_width=True)
    if st.button("Rensa allt och ladda om"):
        st.cache_resource.clear()
        st.session_state.df = load_data()
        st.rerun()
