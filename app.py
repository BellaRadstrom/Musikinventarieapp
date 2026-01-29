import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Musik-Inventering", layout="wide", page_icon="🎸")

st.title("🎸 Musik-Inventering")
st.markdown("Hantera instrument och utrustning smidigt.")

# --- CONNECTION ---
# Vi kör helt rent enligt din önskan för att låta Streamlit Cloud sköta allt via Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    return conn.read(worksheet="Sheet1", ttl="0") # ttl="0" för att alltid hämta färskt vid refresh

# --- UI NAVIGATION ---
tabs = ["Sök & Låna", "Registrera Nytt", "Återlämning", "Admin"]
active_tab = st.sidebar.radio("Meny", tabs)

df = get_data()

# --- TAB: SÖK & LÅNA ---
if active_tab == "Sök & Låna":
    st.header("🔍 Sök i inventariet")
    search_query = st.text_input("Sök på namn eller kategori")
    
    if search_query:
        filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
    else:
        filtered_df = df

    st.dataframe(filtered_df, use_container_width=True)
    
    # Enkel låne-logik (demonstration)
    with st.expander("Boka/Låna objekt"):
        item_to_borrow = st.selectbox("Välj objekt", df['Namn'].tolist() if 'Namn' in df.columns else [])
        user_name = st.text_input("Ditt namn")
        if st.button("Registrera lån"):
            st.success(f"Lån registrerat för {item_to_borrow} till {user_name}!")
            # Här lägger vi till logik för att skriva tillbaka till Sheets senare

# --- TAB: REGISTRERA NYTT ---
elif active_tab == "Registrera Nytt":
    st.header("➕ Lägg till ny utrustning")
    
    with st.form("new_item_form"):
        name = st.text_input("Namn på instrument/utrustning")
        category = st.selectbox("Kategori", ["Stränginstrument", "Trummor", "PA/Ljud", "Kablar", "Övrigt"])
        
        # Kamera- och bilduppladdning
        img_file = st.camera_input("Ta en bild")
        upload_file = st.file_uploader("Eller ladda upp en bild", type=['jpg', 'png'])
        
        submitted = st.form_submit_button("Spara i Google Sheets")
        
        if submitted:
            # Skapa ny rad
            new_row = pd.DataFrame([{
                "Namn": name, 
                "Kategori": category, 
                "Datum": datetime.now().strftime("%Y-%m-%d"),
                "Status": "Tillgänglig"
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("✅ Klart! Inventariet är uppdaterat.")

# --- TAB: ÅTERLÄMNING ---
elif active_tab == "Återlämning":
    st.header("🔄 Återlämning")
    # Här kan man lista lånade objekt och ha en knapp för att "checka in" dem
    st.info("Här listas objekt som är markerade som 'Utlånade'.")

# --- TAB: ADMIN ---
elif active_tab == "Admin":
    st.header("⚙️ Administratörsvy")
    st.write("Fullständig tabellvy:")
    st.dataframe(df)
    
    if st.button("Rensa Cache"):
        st.cache_data.clear()
        st.rerun()
