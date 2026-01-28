import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
import os
from datetime import datetime
import random

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="InstrumentDB", layout="wide")
DB_FILE = "Musikinventarie.csv"

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1a2234; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { background-color: #10b981; color: white; border-radius: 8px; border: none; width: 100%; }
    .stat-card { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- DATA-HANTERING ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"]
    return pd.DataFrame(columns=cols)

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    menu = st.radio("MENY", 
        ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "📝 Hantera & Redigera", "⚙️ System & Export"])
    st.write("---")
    st.success("🟢 System Status: Online")

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='stat-card'>Totalt<br><h2>{len(st.session_state.df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><span style='color:#10b981;'>Tillgängliga</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Tillgänglig'])}</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='stat-card'><span style='color:#f59e0b;'>Utlånade</span><br><h2>{len(st.session_state.df[st.session_state.df['Status'] == 'Utlånad'])}</h2></div>", unsafe_allow_html=True)

    search = st.text_input("", placeholder="Sök...")
    st.write("---")
    
    h_img, h_info, h_qr, h_status, h_owner, h_action = st.columns([1, 2, 1, 1, 1, 1])
    h_img.caption("BILD")
    h_info.caption("INSTRUMENT")
    h_qr.caption("QR / ID")
    h_status.caption("STATUS")
    h_owner.caption("LÅNTAGARE")
    
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    for idx, row in st.session_state.df[mask].iterrows():
        r_img, r_info, r_qr, r_status, r_owner, r_action = st.columns([1, 2, 1, 1, 1, 1])
        
        with r_img:
            if pd.notnull(row['Enhetsfoto']) and str(row['Enhetsfoto']).startswith('http'):
                st.image(row['Enhetsfoto'], width=60)
            else:
                st.write("🖼️")
        
        r_info.write(f"**{row['Modell']}**")
        r_info.caption(row['Tillverkare'])
        
        qr_img = get_qr_image(row['Resurstagg'])
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        r_qr.image(buf, width=45)
        
        st_color = "#dcfce7" if row['Status'] == 'Tillgänglig' else "#fee2e2"
        r_status.markdown(f"<span style='background-color:{st_color}; padding:4px 8px; border-radius:10px;'>{row['Status']}</span>", unsafe_allow_html=True)
        r_owner.write(row['Aktuell ägare'] if pd.notnull(row['Aktuell ägare']) else "—")
        
        if row['Status'] == 'Tillgänglig':
            if r_action.button("➕ Låna", key=f"add_{idx}"):
                if row['Resurstagg'] not in [c['Resurstagg'] for c in st.session_state.cart]:
                    st.session_state.cart.append(row.to_dict())
                    st.toast(f"✅ {row['Modell']} tillagd i korgen!")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Registrera Ny Utrustning")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillv = col2.text_input("Tillverkare")
        tagg = col1.text_input("Resurstagg (Lämna tom för auto-ID)")
        foto = col2.text_input("Bild-URL (valfritt)")
        
        st.info("Kamerabilden används endast under sessionen. För permanent bild, använd Bild-URL.")
        cam = st.camera_input("Ta bild")
        
        submit = st.form_submit_button("💾 SPARA PRODUKT")
        
        if submit:
            if modell:
                final_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                # Kolla om ID redan finns
                if final_id in st.session_state.df['Resurstagg'].values:
                    st.error("Detta ID finns redan! Välj ett annat eller låt fältet vara tomt.")
                else:
                    new_row = {
                        "Modell": modell, 
                        "Tillverkare": tillv, 
                        "Resurstagg": final_id, 
                        "Status": "Tillgänglig", 
                        "Enhetsfoto": foto,
                        "Aktuell ägare": "",
                        "Utlåningsdatum": ""
                    }
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(st.session_state.df)
                    st.success(f"✅ Produkt skapad med ID: {final_id}")
                    st.balloons()
            else:
                st.warning("Du måste minst fylla i Modell.")

# --- VY: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Din Lånekorg")
    if not st.session_state.cart:
        st.info("Korgen är tom. Gå till 'Sök' för att lägga till saker.")
    else:
        st.write("Följande instrument förbereds för utlåning:")
        for item in st.session_state.cart:
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        
        st.write("---")
        name = st.text_input("Vem ska låna? (Namn på låntagare) *")
        date_today = st.date_input("Utlåningsdatum", datetime.now())
        
        if st.button("🚀 SLUTFÖR UTLÅNING"):
            if name:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, date_today.strftime('%Y-%m-%d')]
                save_data(st.session_state.df)
                st.session_state.cart = []
                st.success(f"✅ Utlåningen är registrerad på {name}!")
                st.balloons()
                # Vi väntar lite så användaren hinner se meddelandet innan omladdning
                st.rerun()
            else:
                st.error("❌ Du måste skriva in ett namn på låntagaren!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.selectbox("Välj instrument att returnera:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "] - Lånad av: " + loaned['Aktuell ägare'])
        if st.button("📥 REGISTRERA ÅTERLÄMNING"):
            tag = sel.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', "", ""]
            save_data(st.session_state.df)
            st.success("✅ Instrumentet har återförts till lagret!")
            st.rerun()
    else:
        st.info("Inga instrument är utlånade just nu.")

# --- VY: HANTERA & REDIGERA ---
elif menu == "📝 Hantera & Redigera":
    st.title("Redigera eller Radera")
    if st.session_state.df.empty:
        st.warning("Inventarielistan är tom.")
    else:
        sel = st.selectbox("Välj produkt att ändra:", st.session_state.df['Modell'] + " [" + st.session_state.df['Resurstagg'] + "]")
        if sel:
            tag = sel.split("[")[1].split("]")[0]
            row = st.session_state.df[st.session_state.df['Resurstagg'] == tag].iloc[0]
            
            with st.form("edit_form"):
                new_m = st.text_input("Modell", value=row['Modell'])
                new_t = st.text_input("Tillverkare", value=row['Tillverkare'])
                new_s = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=["Tillgänglig", "Utlånad", "Service"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service"] else 0)
                
                c_save, c_del = st.columns(2)
                
                if c_save.form_submit_button("💾 SPARA ÄNDRINGAR"):
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Modell', 'Tillverkare', 'Status']] = [new_m, new_t, new_status]
                    save_data(st.session_state.df)
                    st.success("✅ Ändringarna sparades!")
                    st.rerun()
                
                if c_del.form_submit_button("🗑️ RADERA PRODUKT PERMANENT"):
                    st.session_state.df = st.session_state.df[st.session_state.df['Resurstagg'] != tag]
                    save_data(st.session_state.df)
                    st.warning(f"Produkten {tag} har raderats.")
                    st.rerun()

# --- VY: SYSTEM & EXPORT ---
elif menu == "⚙️ System & Export":
    st.title("System & Export")
    st.write("Här kan du ladda ner hela databasen som en backup.")
    csv = st.session_state.df.to_csv(index=False).encode('utf-8')
    st.download_button("📂 LADDA NER CSV-BACKUP", csv, f"inventarie_backup_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
