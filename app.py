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

# --- SESSION STATE INITIALISERING ---
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'inv_scanned' not in st.session_state: st.session_state.inv_scanned = []
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{timestamp}] {msg}")

# --- HJÄLPFUNKTIONER ---
def clean_id(val):
    if pd.isna(val) or val == "": return ""
    s = str(val).strip()
    if s.endswith(".0"): s = s[:-2]
    return s

def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((300, 300)) 
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=70)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except Exception as e:
        add_log(f"Bildfel: {e}")
        return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def get_label_html(items):
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-start;'>"
    for item in items:
        qr_b64 = base64.b64encode(generate_qr(item['Resurstagg'])).decode()
        html += f"""
        <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #000; padding: 5px; text-align: center; font-family: Arial, sans-serif; background-color: white; color: black; margin-bottom: 5px;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.6cm;"><br>
            <div style="font-size: 11px; font-weight: bold; margin-top: 2px;">{str(item['Modell'])[:22]}</div>
            <div style="font-size: 9px;">ID: {item['Resurstagg']}</div>
        </div>
        """
    html += "</div><div style='text-align:center; margin-top:20px;'><button onclick='window.print()'>Skriv ut dessa etiketter</button></div>"
    return html

# --- DATALADDNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        if "Resurstagg" in data.columns:
            data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        return data.fillna("")
    except Exception as e:
        add_log(f"Laddningsfel: {e}")
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.cache_data.clear()
        return True
    except Exception as e:
        add_log(f"Sparfel: {e}")
        return False

st.session_state.df = load_data()

# --- NAVIGATION ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- VARUKORG (SIDEBAR) ---
if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']} ({item['Resurstagg']})")
    
    if st.sidebar.button("Töm korg"):
        st.session_state.cart = []
        st.rerun()
        
    borrower_name = st.sidebar.text_input("Vem lånar? *", key="sidebar_borrower")
    if borrower_name:
        if st.sidebar.button("Bekräfta utlån ✅", type="primary"):
            today = datetime.now().strftime("%Y-%m-%d")
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

# --- VY: SÖK & LÅNA (BEHÅLLER ALL TIDIGARE LOGIK) ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            st.subheader(f"Redigerar: {item['Modell']}")
            col_e, col_p = st.columns([2, 1])
            with col_e:
                with st.form("edit_form"):
                    e_mod = st.text_input("Modell", value=item['Modell'])
                    e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], 
                                         index=["Tillgänglig", "Utlånad", "Service"].index(item['Status']) if item['Status'] in ["Tillgänglig", "Utlånad", "Service"] else 0)
                    new_foto = st.camera_input("Uppdatera bild")
                    if st.form_submit_button("Spara ändringar"):
                        st.session_state.df.at[idx, 'Modell'] = e_mod
                        st.session_state.df.at[idx, 'Status'] = e_stat
                        if new_foto: st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_foto)
                        save_data(st.session_state.df)
                        st.session_state.editing_item = None
                        st.rerun()
                if st.button("Avbryt"): 
                    st.session_state.editing_item = None
                    st.rerun()
            with col_p:
                st.components.v1.html(get_label_html([item.to_dict()]), height=250)

    query = st.text_input("Sök i lagret...")
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=80)
            with c2:
                st.write(f"**{row['Modell']}**")
                st.caption(f"{row['Typ']} | ID: {row['Resurstagg']}")
            with c3:
                st.image(generate_qr(row['Resurstagg']), width=60)
            with c4:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT (UPPDATERAD) ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt objekt")
    
    # Session state för att hålla temporära värden om man genererar nummer
    if 'gen_sn' not in st.session_state: st.session_state.gen_sn = ""
    if 'gen_id' not in st.session_state: st.session_state.gen_id = ""

    with st.form("full_reg", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            m = st.text_input("Modell *")
            t_verk = st.text_input("Tillverkare")
            typ = st.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Övrigt"])
            farg = st.text_input("Färg")
            
        with col2:
            sn = st.text_input("Serienummer *", help="Om serienummer saknas, lämna tomt och använd knappen nedan efteråt eller skriv 'SAKNAS'")
            rid = st.text_input("Resurstagg (ID) *", help="Lämna tomt för att generera ett unikt ID")
            skod = st.text_input("Streckkod (valfritt)")
            
        foto = st.camera_input("Produktfoto")
        
        submit = st.form_submit_button("Spara till lager")
        
        if submit:
            # Validering och automatisk generering vid behov
            final_sn = sn if sn else f"SYS-{random.randint(1000, 9999)}"
            final_rid = clean_id(rid) if rid else str(random.randint(100000, 999999))
            
            if m:
                new_row = {
                    "Enhetsfoto": process_image_to_base64(foto) if foto else "",
                    "Modell": m,
                    "Tillverkare": t_verk,
                    "Typ": typ,
                    "Färg": farg,
                    "Resurstagg": final_rid,
                    "Streckkod": skod,
                    "Serienummer": final_sn,
                    "Status": "Tillgänglig",
                    "Aktuell ägare": "",
                    "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"Sparad! ID: {final_rid}, SN: {final_sn}")
            else:
                st.error("Modellnamn måste fyllas i!")

# --- VY: ÅTERLÄMNING (BATCH-LÄGE BEHÅLLS) ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning per person")
    active_borrowers = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    
    if len(active_borrowers) > 0:
        selected_borrower = st.selectbox("Välj person:", ["--- Välj ---"] + list(active_borrowers))
        if selected_borrower != "--- Välj ---":
            borrowed_items = st.session_state.df[st.session_state.df['Aktuell ägare'] == selected_borrower]
            return_list = []
            for i, row in borrowed_items.iterrows():
                if st.checkbox(f"{row['Modell']} (ID: {row['Resurstagg']})", value=True, key=f"ret_{row['Resurstagg']}"):
                    return_list.append(row['Resurstagg'])
            
            if st.button("Bekräfta inlämning", type="primary"):
                for tid in return_list:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                save_data(st.session_state.df)
                st.rerun()
    else: st.info("Inga utlånade objekt.")

# --- VY: ADMIN (BULK-QR OCH LOGG BEHÅLLS) ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Administration")
    t1, t2, t3, t4 = st.tabs(["📊 Lager", "📋 Inventering", "🏷️ Bulk-etiketter", "🛠️ Logg"])
    
    with t1:
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
    
    with t3:
        all_opts = st.session_state.df.apply(lambda r: f"{r['Modell']} | ID:{r['Resurstagg']}", axis=1).tolist()
        selected_bulk = st.multiselect("Välj produkter:", all_opts)
        if selected_bulk:
            to_print = []
            for opt in selected_bulk:
                tag = opt.split("| ID:")[-1]
                match = st.session_state.df[st.session_state.df['Resurstagg'] == tag]
                if not match.empty: to_print.append(match.iloc[0].to_dict())
            if to_print and st.button("Generera etiketter"):
                st.components.v1.html(get_label_html(to_print), height=600, scrolling=True)

    with t4:
        for log in reversed(st.session_state.debug_log): st.text(log)
