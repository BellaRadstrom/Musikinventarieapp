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

# --- SESSION STATE ---
if 'cart' not in st.session_state: st.session_state.cart = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'scanned_code' not in st.session_state: st.session_state.scanned_code = ""

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

# --- VARUKORG ---
if st.session_state.cart:
    st.sidebar.subheader("🛒 Varukorg")
    for i in st.session_state.cart: st.sidebar.caption(f"• {i['Modell']}")
    borrower = st.sidebar.text_input("Vem lånar?")
    if st.sidebar.button("Slutför utlån") and borrower:
        today = datetime.now().strftime("%Y-%m-%d")
        for item in st.session_state.cart:
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
        save_data(st.session_state.df)
        st.session_state.cart = []
        st.rerun()

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # Skanner-logik som använder en dold HTML-input för att trigga Streamlit
    with st.expander("📷 Starta QR-skanner", expanded=True):
        qr_component_js = f"""
        <div id="reader" style="width: 100%; max-width: 400px; margin: auto; border: 2px solid #ccc; border-radius: 10px; overflow: hidden;"></div>
        <p id="feedback" style="text-align: center; font-family: sans-serif; font-weight: bold; color: #666; margin-top: 10px;">Siktar...</p>
        
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText) {{
                document.getElementById('feedback').innerText = "TRÄFF: " + decodedText;
                document.getElementById('feedback').style.color = "#4CAF50";
                
                // Denna rad pratar direkt med Streamlits inbyggda meddelandesystem
                const event = new CustomEvent("QR_SCANNED", {{ detail: decodedText }});
                window.parent.document.dispatchEvent(event);
                
                // Fallback: Ändra URL om eventet blockeras
                const url = new URL(window.parent.location.href);
                url.searchParams.set('qr_code', decodedText);
                window.parent.location.href = url.href;
            }}
            
            const html5QrCode = new Html5Qrcode("reader");
            const config = {{ fps: 10, qrbox: {{width: 250, height: 250}}, aspectRatio: 1.0 }};
            html5QrCode.start({{ facingMode: "environment" }}, config, onScanSuccess);
        </script>
        """
        st.components.v1.html(qr_component_js, height=480)

    # Fånga upp koden från URL (fungerar som den mest stabila bryggan på mobiler)
    url_code = st.query_params.get("qr_code", "")
    
    query = st.text_input("Sök produkt eller ID", value=url_code, key="search_field")
    
    if url_code and st.button("Rensa skanning"):
        st.query_params.clear()
        st.rerun()

    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data"): st.image(row['Enhetsfoto'], width=100)
            with c2:
                st.markdown(f"### {row['Modell']}")
                st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
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
    st.header("Återlämning")
    borrowers = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    if len(borrowers) > 0:
        target = st.selectbox("Vem lämnar tillbaka?", borrowers)
        items = st.session_state.df[st.session_state.df['Aktuell ägare'] == target]
        for i, row in items.iterrows():
            if st.button(f"Lämna tillbaka {row['Modell']} ({row['Resurstagg']})", key=f"ret_{i}"):
                st.session_state.df.at[i, 'Status'] = 'Tillgänglig'
                st.session_state.df.at[i, 'Aktuell ägare'] = ''
                save_data(st.session_state.df)
                st.rerun()
    else: st.info("Inga aktiva utlån.")

# --- VY: REGISTRERA ---
elif menu == "➕ Registrera Nytt":
    if not st.session_state.authenticated: st.warning("Logga in för att registrera.")
    else:
        with st.form("new"):
            m = st.text_input("Modell *")
            i = st.text_input("ID/SN *")
            f = st.camera_input("Foto")
            if st.form_submit_button("Spara"):
                new_row = {"Modell": m, "Resurstagg": clean_id(i), "Status": "Tillgänglig", "Enhetsfoto": process_image_to_base64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparad!")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    if not st.session_state.authenticated: st.warning("Logga in.")
    else:
        tab1, tab2, tab3 = st.tabs(["📊 Lager", "🏷️ Bulk QR", "📋 Inventering"])
        with tab1:
            st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
        with tab2:
            st.subheader(" Bulk-utskrift av QR")
            sel = st.multiselect("Välj produkter:", st.session_state.df['Modell'].tolist())
            if sel:
                to_p = st.session_state.df[st.session_state.df['Modell'].isin(sel)].to_dict('records')
                st.components.v1.html(get_label_html(to_p), height=500, scrolling=True)
        with tab3:
            st.write("Senast inventerad lista")
            st.write(st.session_state.df[['Modell', 'Resurstagg', 'Senast inventerad']])
