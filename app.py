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

def get_packing_list_html(borrower, items):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    list_items = "".join([f"<li>{item['Modell']} (SN: {item['Serienummer']})</li>" for item in items])
    return f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ccc; background: white; color: black;">
        <h2>📦 Packlista / Lånekvitto</h2>
        <p><b>Låntagare:</b> {borrower}</p>
        <p><b>Datum:</b> {date_str}</p>
        <hr>
        <ul>{list_items}</ul>
        <button onclick="window.print()">Skriv ut packlista</button>
    </div>
    """

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
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Resurstagg", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

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
            st.session_state.last_checkout = {"borrower": borrower_name, "items": list(st.session_state.cart)}
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

if st.session_state.last_checkout:
    with st.sidebar.expander("📄 Senaste packlista", expanded=True):
        if st.button("Visa packlista"):
            st.components.v1.html(get_packing_list_html(st.session_state.last_checkout['borrower'], st.session_state.last_checkout['items']), height=350)

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            st.subheader(f"Redigerar: {item['Modell']}")
            col_e, col_p = st.columns([2, 1])
            with col_e:
                with st.form("edit_product_form"):
                    e_mod = st.text_input("Modellnamn", value=item['Modell'])
                    e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], 
                                         index=["Tillgänglig", "Utlånad", "Service"].index(item['Status']) if item['Status'] in ["Tillgänglig", "Utlånad", "Service"] else 0)
                    st.write("📸 **Uppdatera bild**")
                    new_foto = st.camera_input("Ta nytt foto")
                    
                    if st.form_submit_button("Spara alla ändringar"):
                        st.session_state.df.at[idx, 'Modell'] = e_mod
                        st.session_state.df.at[idx, 'Status'] = e_stat
                        if new_foto:
                            st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_foto)
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
                st.caption(f"ID: {row['Resurstagg']} | SN: {row['Serienummer']}")
            with c3:
                st.image(generate_qr(row['Resurstagg']), width=60)
            with c4:
                if row['Status'] == 'Tillgänglig':
                    if any(item['Resurstagg'] == row['Resurstagg'] for item in st.session_state.cart):
                        st.info("I korgen")
                    elif st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                else: st.write(f"🚫 {row['Status']}")
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    with st.form("new_reg"):
        m = st.text_input("Modell *")
        s = st.text_input("Serienummer *")
        t = st.text_input("ID (Lämna tom för auto)")
        foto = st.camera_input("Foto")
        if st.form_submit_button("Spara"):
            if m and s:
                rid = clean_id(t) if t else str(random.randint(100000, 999999))
                new_row = {"Enhetsfoto": process_image_to_base64(foto) if foto else "", "Modell": m, "Serienummer": s, "Resurstagg": rid, "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"Klar! ID: {rid}")

# --- VY: ÅTERLÄMNING (UPPDATERAD TILL BATCH-LÄGE) ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning per person")
    
    # Hitta alla unika låntagare
    active_borrowers = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    
    if len(active_borrowers) > 0:
        selected_borrower = st.selectbox("Välj person som lämnar tillbaka:", ["--- Välj person ---"] + list(active_borrowers))
        
        if selected_borrower != "--- Välj person ---":
            # Hämta alla objekt för denna person
            borrowed_items = st.session_state.df[st.session_state.df['Aktuell ägare'] == selected_borrower]
            
            st.subheader(f"Produkter utlånade till {selected_borrower}")
            st.write("Avmarkera de objekt som INTE lämnas in:")
            
            # Skapa en checklista
            return_list = []
            for i, row in borrowed_items.iterrows():
                is_checked = st.checkbox(f"{row['Modell']} (ID: {row['Resurstagg']})", value=True, key=f"ret_{row['Resurstagg']}")
                if is_checked:
                    return_list.append(row['Resurstagg'])
            
            if st.button(f"Bekräfta inlämning av {len(return_list)} objekt", type="primary"):
                if len(return_list) > 0:
                    for tid in return_list:
                        st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, 
                                                ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                    
                    if save_data(st.session_state.df):
                        st.success(f"Inlämning klar för {selected_borrower}!")
                        st.rerun()
                else:
                    st.warning("Inga objekt valda för inlämning.")
    else:
        st.info("Inga utlånade objekt i systemet just nu.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Administration")
    t1, t2, t3, t4 = st.tabs(["📊 Lager", "📋 Inventering", "🏷️ Bulk-etiketter", "🛠️ Logg"])
    
    with t1:
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
    
    with t3:
        st.subheader("Massutskrift")
        all_opts = st.session_state.df.apply(lambda r: f"{r['Modell']} | ID:{r['Resurstagg']}", axis=1).tolist()
        selected_bulk = st.multiselect("Välj produkter:", all_opts)
        
        if selected_bulk:
            to_print = []
            for opt in selected_bulk:
                tag = opt.split("| ID:")[-1]
                match = st.session_state.df[st.session_state.df['Resurstagg'] == tag]
                if not match.empty:
                    to_print.append(match.iloc[0].to_dict())
            
            if to_print and st.button("Generera"):
                st.components.v1.html(get_label_html(to_print), height=600, scrolling=True)

    with t4:
        st.subheader("Systemlogg")
        if st.button("Rensa logg"): st.session_state.debug_log = []
        for log in reversed(st.session_state.debug_log):
            st.text(log)
