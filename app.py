import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64

# --- CONFIG ---
st.set_page_config(page_title="Musik-IT Birka", layout="wide", page_icon="🎸")

# --- SESSION STATE INITIALISERING ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'debug_logs' not in st.session_state: st.session_state.debug_logs = []

# --- HJÄLPFUNKTIONER ---
def add_log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_logs.append(f"[{now}] {msg}")

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
        add_log(f"Fotofel: {str(e)}")
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
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px;'>"
    for item in items:
        qr_b64 = base64.b64encode(generate_qr(item['Resurstagg'])).decode()
        html += f"""
        <div style="width: 3.5cm; height: 2.5cm; border: 1px solid #000; padding: 5px; text-align: center; background: white; color: black;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.4cm;"><br>
            <b style="font-size: 10px;">{str(item['Modell'])[:20]}</b><br>
            <span style="font-size: 8px;">ID: {item['Resurstagg']}</span>
        </div>"""
    html += "</div><br><button onclick='window.print()'>Skriv ut etiketter</button>"
    return html

# --- DATALADDNING ---
def load_data_from_gsheets():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        data = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in cols:
            if col not in data.columns: data[col] = ""
        data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        st.session_state.df = data.fillna("")
        add_log("Data synkad med GSheets.")
    except Exception as e:
        add_log(f"Laddningsfel: {str(e)}")

def save_data(df):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.session_state.df = df
        add_log("GSheets uppdaterad.")
    except Exception as e:
        add_log(f"Spara-fel: {str(e)}")

# --- STARTA APPLIKATIONEN ---
if st.session_state.df is None:
    load_data_from_gsheets()

# --- SIDEBAR & VARUKORG ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Lösenord", type="password")
st.session_state.authenticated = (pwd == "Birka")

if st.session_state.cart:
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']} ({item['Resurstagg']})")
    
    borrower = st.sidebar.text_input("Vem lånar?", key="borrower_name")
    if st.sidebar.button("Slutför utlån", type="primary"):
        if borrower:
            today = datetime.now().strftime("%Y-%m-%d")
            for cart_item in st.session_state.cart:
                # Uppdatera status i sessionen
                idx = st.session_state.df[st.session_state.df['Resurstagg'] == cart_item['Resurstagg']].index
                st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
            
            save_data(st.session_state.df)
            st.session_state.cart = []
            st.sidebar.success(f"Utlånat till {borrower}!")
            st.rerun()
        else:
            st.sidebar.error("Ange ett namn!")

if st.sidebar.button("Rensa varukorg"):
    st.session_state.cart = []
    st.rerun()

menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Nytt", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    with st.expander("📷 QR-Skanner", expanded=True):
        qr_js = """
        <div id="reader" style="width: 100%; max-width: 400px; margin: auto; border: 2px solid #ccc; border-radius: 10px; overflow: hidden; background: #f0f0f0;"></div>
        <p id="scan-msg" style="text-align: center; font-weight: bold; margin-top: 10px;">Siktar...</p>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText) {
                document.getElementById('scan-msg').innerText = "KOD HITTAD: " + decodedText;
                document.getElementById('scan-msg').style.color = "green";
                localStorage.setItem('birka_qr', decodedText);
                if(navigator.vibrate) navigator.vibrate(70);
            }
            const html5QrCode = new Html5Qrcode("reader");
            html5QrCode.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, onScanSuccess);
        </script>
        """
        st.components.v1.html(qr_js, height=420)

    if st.button("📥 HÄMTA SKANNAD KOD TILL SÖKRUTAN", use_container_width=True, type="primary"):
        # Fix för Pixel: Använder window.parent för att nå huvudfönstret från iframen
        js_bridge = """
        <script>
            const code = localStorage.getItem('birka_qr');
            if (code) {
                const url = new URL(window.parent.location.href);
                url.searchParams.set('search', code);
                window.parent.location.href = url.href;
            } else {
                alert("Skanna en kod först!");
            }
        </script>
        """
        st.components.v1.html(js_bridge, height=0)

    # Hämta värdet från URL
    scanned_val = st.query_params.get("search", "")
    query = st.text_input("Sök produkt eller ID", value=scanned_val)
    
    if scanned_val and st.button("Rensa sökning"):
        st.query_params.clear()
        st.rerun()

    if st.session_state.df is not None:
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

        for idx, row in results.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    if str(row['Enhetsfoto']).startswith("data"): st.image(row['Enhetsfoto'], width=100)
                with c2:
                    st.markdown(f"### {row['Modell']}")
                    st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                    if row['Status'] == 'Utlånad':
                        st.info(f"Låntagare: {row['Aktuell ägare']} ({row['Utlåningsdatum']})")
                with c3:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Lägg i vagn", key=f"btn_{idx}"):
                            if not any(item['Resurstagg'] == row['Resurstagg'] for item in st.session_state.cart):
                                st.session_state.cart.append(row.to_dict())
                                st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowed_items = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    
    if not borrowed_items.empty:
        for idx, row in borrowed_items.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Modell']}** (ID: {row['Resurstagg']})")
                st.caption(f"Lånad av: {row['Aktuell ägare']}")
                if st.button(f"Registrera återlämning", key=f"ret_{idx}"):
                    st.session_state.df.at[idx, 'Status'] = 'Tillgänglig'
                    st.session_state.df.at[idx, 'Aktuell ägare'] = ''
                    st.session_state.df.at[idx, 'Utlåningsdatum'] = ''
                    st.session_state.df.at[idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_data(st.session_state.df)
                    st.success("Återlämnad!")
                    st.rerun()
    else:
        st.info("Inga prylar är utlånade just nu.")

# --- VY: REGISTRERA ---
elif menu == "➕ Registrera Nytt":
    if not st.session_state.authenticated: st.warning("Logga in för att registrera.")
    else:
        with st.form("new_item"):
            m = st.text_input("Modell *")
            i = st.text_input("ID/Resurstagg *")
            t = st.text_input("Tillverkare")
            f = st.camera_input("Ta foto")
            if st.form_submit_button("Spara produkt"):
                new_data = {"Modell": m, "Resurstagg": clean_id(i), "Tillverkare": t, "Status": "Tillgänglig", "Enhetsfoto": process_image_to_base64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparad i registret!")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    if not st.session_state.authenticated: st.warning("Logga in.")
    else:
        tab1, tab2, tab3 = st.tabs(["📊 Lagerlista", "🏷️ Bulk QR-etiketter", "📋 Logg & Debug"])
        with tab1:
            st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
        with tab2:
            sel = st.multiselect("Välj prylar för etiketter:", st.session_state.df['Modell'].tolist())
            if sel:
                to_print = st.session_state.df[st.session_state.df['Modell'].isin(sel)].to_dict('records')
                st.components.v1.html(get_label_html(to_print), height=500, scrolling=True)
        with tab3:
            if st.button("Tvinga omladdning från Google Sheets"):
                load_data_from_gsheets()
                st.rerun()
            st.write("URL Parametrar:", st.query_params.to_dict())
            for log in st.session_state.debug_logs:
                st.text(log)import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64

# --- CONFIG ---
st.set_page_config(page_title="Musik-IT Birka", layout="wide", page_icon="🎸")

# --- SESSION STATE ---
if 'cart' not in st.session_state: st.session_state.cart = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

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
    except: return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def get_label_html(items):
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px;'>"
    for item in items:
        qr_b64 = base64.b64encode(generate_qr(item['Resurstagg'])).decode()
        html += f"""
        <div style="width: 3.5cm; height: 2.5cm; border: 1px solid #000; padding: 5px; text-align: center; background: white; color: black;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.4cm;"><br>
            <b style="font-size: 10px;">{str(item['Modell'])[:20]}</b><br>
            <span style="font-size: 8px;">ID: {item['Resurstagg']}</span>
        </div>"""
    html += "</div><br><button onclick='window.print()'>Skriv ut etiketter</button>"
    return html

# --- DATALADDNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in cols:
            if col not in data.columns: data[col] = ""
        data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        return data.fillna("")
    except: return pd.DataFrame()

st.session_state.df = load_data()

def save_data(df):
    conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
    st.cache_data.clear()

# --- LOGIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Lösenord för Admin/Edit", type="password")
st.session_state.authenticated = (pwd == "Birka")

menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Nytt", "⚙️ Admin"])

# --- VARUKORG & PACKLISTA ---
if st.session_state.cart:
    st.sidebar.subheader("🛒 Varukorg")
    for i in st.session_state.cart: st.sidebar.caption(f"• {i['Modell']}")
    borrower = st.sidebar.text_input("Vem lånar?")
    if st.sidebar.button("Slutför utlån") and borrower:
        today = datetime.now().strftime("%Y-%m-%d")
        st.session_state.last_checkout = {"borrower": borrower, "items": list(st.session_state.cart)}
        for item in st.session_state.cart:
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
        save_data(st.session_state.df)
        st.session_state.cart = []
        st.rerun()

if st.session_state.last_checkout:
    st.sidebar.success(f"Lån klart till {st.session_state.last_checkout['borrower']}")
    list_items_html = "".join([f"<li>{i['Modell']} ({i['Resurstagg']})</li>" for i in st.session_state.last_checkout['items']])
    print_js = f"""
    <script>
    function printList() {{
        var win = window.open('', '_blank', 'height=700,width=700');
        win.document.write('<html><head><title>Packlista</title></head><body style="font-family:sans-serif; padding:50px;">');
        win.document.write('<h1>Packlista - Birka Musik-IT</h1>');
        win.document.write('<p><b>Låntagare:</b> {st.session_state.last_checkout['borrower']}</p>');
        win.document.write('<p><b>Datum:</b> {datetime.now().strftime("%Y-%m-%d")}</p><hr><ul>');
        win.document.write('{list_items_html}');
        win.document.write('</ul><hr><p>Tack!</p>');
        win.document.write('</body></html>');
        win.document.close();
        setTimeout(function() {{ win.print(); }}, 500);
    }}
    </script>
    <button onclick="printList()" style="width:100%; padding:10px; background:#4CAF50; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">🖨️ SKRIV UT PACKLISTA</button>
    """
    with st.sidebar:
        st.components.v1.html(print_js, height=60)

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    scanned_qr = st.query_params.get("qr", "")
    
    with st.expander("📷 Starta QR-skanner", expanded=not bool(scanned_qr)):
        qr_js = """
        <div style="display: flex; justify-content: center; flex-direction: column; align-items: center;">
            <div id="reader" style="width: 100%; max-width: 400px; border: 2px solid #ccc; border-radius: 8px; overflow: hidden;"></div>
        </div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText) {
                const url = new URL(window.top.location.href);
                url.searchParams.set('qr', decodedText);
                window.top.location.href = url.href;
            }
            let html5QrCode = new Html5Qrcode("reader");
            const config = { 
                fps: 25, 
                qrbox: {width: 280, height: 280},
                videoConstraints: { 
                    facingMode: "environment",
                    focusMode: "continuous",
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                } 
            };
            html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess)
            .catch(err => console.error("Kamerafel", err));
        </script>"""
        st.components.v1.html(qr_js, height=450)

    query = st.text_input("Sök produkt eller ID", value=scanned_qr)
    if scanned_qr and st.button("Rensa sökning"):
        st.query_params.clear()
        st.rerun()

    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

    if st.session_state.editing_item is not None and st.session_state.authenticated:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.form("edit_form"):
            st.subheader(f"Redigera {item['Modell']}")
            c1, c2 = st.columns(2)
            u_mod = c1.text_input("Modell", value=item['Modell'])
            u_tverk = c1.text_input("Tillverkare", value=item['Tillverkare'])
            u_typ = c1.text_input("Typ", value=item['Typ'])
            u_farg = c2.text_input("Färg", value=item['Färg'])
            u_id = c2.text_input("Resurstagg/ID", value=item['Resurstagg'])
            u_skod = c2.text_input("Streckkod", value=item['Streckkod'])
            u_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
            
            if st.form_submit_button("Spara ändringar"):
                st.session_state.df.at[idx, 'Modell'] = u_mod
                st.session_state.df.at[idx, 'Tillverkare'] = u_tverk
                st.session_state.df.at[idx, 'Typ'] = u_typ
                st.session_state.df.at[idx, 'Färg'] = u_farg
                st.session_state.df.at[idx, 'Resurstagg'] = clean_id(u_id)
                st.session_state.df.at[idx, 'Streckkod'] = u_skod
                st.session_state.df.at[idx, 'Status'] = u_stat
                save_data(st.session_state.df)
                st.session_state.editing_item = None
                st.rerun()
        if st.button("Avbryt"):
            st.session_state.editing_item = None
            st.rerun()

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data"): st.image(row['Enhetsfoto'], width=100)
            with c2:
                st.markdown(f"### {row['Modell']}")
                st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                if row['Status'] == 'Utlånad':
                    st.caption(f"Lånad av: {row['Aktuell ägare']} ({row['Utlåningsdatum']})")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.session_state.authenticated:
                    if st.button("✏️ Edit", key=f"e_{idx}"):
                        st.session_state.editing_item = idx
                        st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning & Inventering")
    borrowers = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    
    if len(borrowers) > 0:
        target = st.selectbox("Välj person som lämnar tillbaka:", borrowers)
        items_to_return = st.session_state.df[st.session_state.df['Aktuell ägare'] == target]
        
        st.write(f"Produkter utlånade till {target}:")
        selected_tags = []
        for i, row in items_to_return.iterrows():
            if st.checkbox(f"{row['Modell']} (ID: {row['Resurstagg']}) - Lånad: {row['Utlåningsdatum']}", key=f"ret_{row['Resurstagg']}"):
                selected_tags.append(row['Resurstagg'])
        
        if st.button("Registrera återlämning av valda") and selected_tags:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            for tag in selected_tags:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = ['Tillgänglig', '', '', now]
            save_data(st.session_state.df)
            st.success("Produkter återställda!")
            st.rerun()
    else: st.info("Inga aktiva utlån.")

# --- VY: REGISTRERA ---
elif menu == "➕ Registrera Nytt":
    if not st.session_state.authenticated: st.warning("Logga in för att registrera.")
    else:
        st.header("Ny produkt")
        with st.form("new"):
            c1, c2 = st.columns(2)
            m = c1.text_input("Modell *")
            i = c1.text_input("ID/SN *")
            t = c2.text_input("Tillverkare")
            ty = c2.text_input("Typ")
            f = st.camera_input("Foto")
            if st.form_submit_button("Spara"):
                new_row = {"Modell": m, "Resurstagg": clean_id(i), "Tillverkare": t, "Typ": ty, "Status": "Tillgänglig", "Enhetsfoto": process_image_to_base64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparad!")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    if not st.session_state.authenticated: st.warning("Logga in med lösenordet Birka.")
    else:
        tab1, tab2, tab3 = st.tabs(["📊 Lager", "📋 Inventering", "🏷️ Bulk QR"])
        with tab1:
            st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]), use_container_width=True)
        with tab2:
            st.subheader("Snabb-inventera via skanning")
            inv_id = st.text_input("Skanna ID för att markera som OK")
            if inv_id:
                cid = clean_id(inv_id)
                if cid in st.session_state.df['Resurstagg'].values:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == cid, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_data(st.session_state.df)
                    st.success(f"Inventerat {cid}")
            st.write(st.session_state.df[['Modell', 'Resurstagg', 'Senast inventerad', 'Status']])
        with tab3:
            st.subheader("Bulk-utskrift av QR")
            sel = st.multiselect("Välj produkter:", st.session_state.df['Modell'].tolist())
            if sel:
                to_p = st.session_state.df[st.session_state.df['Modell'].isin(sel)].to_dict('records')
                st.components.v1.html(get_label_html(to_p), height=500, scrolling=True)


