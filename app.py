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
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'inv_scanned' not in st.session_state: st.session_state.inv_scanned = []
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None
if 'temp_sn' not in st.session_state: st.session_state.temp_sn = ""
if 'qr_scan_result' not in st.session_state: st.session_state.qr_scan_result = ""

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
            <div style="font-size: 9px;">ID/SN: {item['Resurstagg']}</div>
        </div>
        """
    html += "</div><div style='text-align:center; margin-top:10px;'><button onclick='window.print()'>Skriv ut etiketter</button></div>"
    return html

def get_packing_list_html(borrower, items):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    list_items = "".join([f"<li style='padding:5px 0;'><b>{item['Modell']}</b><br><small>SN/ID: {item['Resurstagg']}</small></li>" for item in items])
    return f"""
    <div style="font-family: Arial, sans-serif; padding: 30px; border: 2px solid #333; background: white; color: black; max-width: 600px; margin: auto;">
        <h1>🎸 Utlåningskvitto</h1>
        <p><b>Låntagare:</b> {borrower}</p>
        <p><b>Datum:</b> {date_str}</p>
        <hr>
        <h3>Utrustning:</h3>
        <ul>{list_items}</ul>
        <button onclick="window.print()">🖨️ Skriv ut</button>
    </div>
    """

# --- ANSLUTNING ---
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

# --- SIDEBAR ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']} ({item['Resurstagg']})")
    if st.sidebar.button("Töm korg"):
        st.session_state.cart = []
        st.rerun()
    borrower_name = st.sidebar.text_input("Vem lånar? *")
    if borrower_name and st.sidebar.button("Bekräfta utlån ✅", type="primary"):
        today = datetime.now().strftime("%Y-%m-%d")
        st.session_state.last_checkout = {"borrower": borrower_name, "items": list(st.session_state.cart)}
        for item in st.session_state.cart:
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
        if save_data(st.session_state.df):
            st.session_state.cart = []
            st.rerun()

if st.session_state.last_checkout:
    with st.sidebar.expander("📄 Packlista", expanded=True):
        if st.button("Visa för utskrift"):
            st.components.v1.html(get_packing_list_html(st.session_state.last_checkout['borrower'], st.session_state.last_checkout['items']), height=400)

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # Webb-baserad QR-skanner (JavaScript)
    with st.expander("📷 Öppna QR-skanner"):
        st.markdown("""
        <div id="reader" style="width: 100%;"></div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText, decodedResult) {
                // Skicka resultatet till Streamlit genom att skapa en länk eller ändra URL
                window.parent.postMessage({
                    type: 'streamlit:set_widget_value',
                    data: {id: 'qr_input_field', value: decodedText}
                }, '*');
                // Stoppa skannern efter lyckad läsning
                html5QrcodeScanner.clear();
            }
            let html5QrcodeScanner = new Html5QrcodeScanner(
                "reader", { fps: 10, qrbox: 250 });
            html5QrcodeScanner.render(onScanSuccess);
        </script>
        """, unsafe_allow_html=True)

    # Sökfält (här hamnar skannat värde)
    query = st.text_input("Sök produkt eller skanna QR...", key="qr_input_field", placeholder="Skriv här eller skanna ovan...")
    
    if query:
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
    else:
        results = st.session_state.df

    # Redigeringsläge
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            st.subheader(f"✏️ Redigerar: {item['Modell']}")
            with st.form("complete_edit"):
                c1, c2 = st.columns(2)
                with c1:
                    u_mod = st.text_input("Modell", value=item['Modell'])
                    u_tverk = st.text_input("Tillverkare", value=item['Tillverkare'])
                    u_typ = st.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Övrigt"], 
                                        index=["Instrument", "PA", "Mikrofoner", "Övrigt"].index(item['Typ']) if item['Typ'] in ["Instrument", "PA", "Mikrofoner", "Övrigt"] else 0)
                with c2:
                    u_sn = st.text_input("Serienummer / ID", value=item['Resurstagg'])
                    u_farg = st.text_input("Färg", value=item['Färg'])
                    u_skod = st.text_input("Streckkod", value=item['Streckkod'])
                
                u_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], 
                                     index=["Tillgänglig", "Utlånad", "Service"].index(item['Status']) if item['Status'] in ["Tillgänglig", "Utlånad", "Service"] else 0)
                
                new_img = st.camera_input("Ändra foto")
                
                if st.form_submit_button("Spara alla ändringar"):
                    st.session_state.df.at[idx, 'Modell'] = u_mod
                    st.session_state.df.at[idx, 'Tillverkare'] = u_tverk
                    st.session_state.df.at[idx, 'Typ'] = u_typ
                    st.session_state.df.at[idx, 'Resurstagg'] = u_sn
                    st.session_state.df.at[idx, 'Serienummer'] = u_sn
                    st.session_state.df.at[idx, 'Färg'] = u_farg
                    st.session_state.df.at[idx, 'Streckkod'] = u_skod
                    st.session_state.df.at[idx, 'Status'] = u_stat
                    
                    if new_img:
                        st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_img)
                    
                    if save_data(st.session_state.df):
                        st.success("Ändringar sparade!")
                        st.session_state.editing_item = None
                        st.rerun()
            if st.button("Avbryt"):
                st.session_state.editing_item = None
                st.rerun()

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=90)
            with c2:
                color = "green" if row['Status'] == 'Tillgänglig' else "red"
                st.markdown(f"### {row['Modell']}")
                st.markdown(f":{color}[● {row['Status']}] | {row['Typ']} | SN: {row['Serienummer']}")
            with c3:
                st.image(generate_qr(row['Resurstagg']), width=60)
            with c4:
                if row['Status'] == 'Tillgänglig':
                    if any(c['Resurstagg'] == row['Resurstagg'] for c in st.session_state.cart):
                        st.success("I korg")
                    elif st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"Tillagd: {row['Modell']}")
                        st.rerun()
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    if st.button("✨ Generera unikt Serienummer"):
        st.session_state.temp_sn = f"SN-{random.randint(10000, 99999)}"
        st.rerun()

    with st.form("new_reg", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            m_in = st.text_input("Modell *")
            t_in = st.text_input("Tillverkare")
            typ_in = st.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Övrigt"])
        with c2:
            sn_in = st.text_input("Serienummer / ID *", value=st.session_state.temp_sn)
            farg_in = st.text_input("Färg")
            skod_in = st.text_input("Streckkod")
        
        foto_in = st.camera_input("Produktfoto")
        
        if st.form_submit_button("Spara"):
            if m_in and sn_in:
                new_id = clean_id(sn_in)
                new_row = {
                    "Enhetsfoto": process_image_to_base64(foto_in) if foto_in else "",
                    "Modell": m_in, "Tillverkare": t_in, "Typ": typ_in, "Färg": farg_in,
                    "Resurstagg": new_id, "Serienummer": new_id, "Streckkod": skod_in,
                    "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.session_state.temp_sn = ""
                    st.success(f"Sparad: {m_in}")
            else:
                st.error("Modell och Serienummer krävs!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    active_b = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    if len(active_b) > 0:
        target = st.selectbox("Välj person:", ["--- Välj ---"] + list(active_b))
        if target != "--- Välj ---":
            items = st.session_state.df[st.session_state.df['Aktuell ägare'] == target]
            to_ret = []
            for i, r in items.iterrows():
                if st.checkbox(f"{r['Modell']} ({r['Resurstagg']})", value=True, key=f"r_{r['Resurstagg']}"):
                    to_ret.append(r['Resurstagg'])
            if st.button("Bekräfta", type="primary"):
                for tid in to_ret:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                save_data(st.session_state.df)
                st.success("Återlämnat!")
                st.rerun()
    else: st.info("Inga utlånade objekt.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Administration")
    t1, t2, t3 = st.tabs(["📊 Lagerlista", "🏷️ Bulk-etiketter", "🛠️ Logg"])
    with t1:
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]), use_container_width=True)
    with t2:
        opts = st.session_state.df.apply(lambda r: f"{r['Modell']} | SN:{r['Serienummer']}", axis=1).tolist()
        sel = st.multiselect("Välj för utskrift:", opts)
        if sel:
            to_p = []
            for o in sel:
                tag = o.split("| SN:")[-1]
                match = st.session_state.df[st.session_state.df['Resurstagg'] == tag]
                if not match.empty: to_p.append(match.iloc[0].to_dict())
            if st.button("Generera"):
                st.components.v1.html(get_label_html(to_p), height=600, scrolling=True)
    with t3:
        for log in reversed(st.session_state.debug_log): st.text(log)
