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
    <div style="font-family: 'Helvetica Neue', Arial, sans-serif; padding: 30px; border: 2px solid #333; background: white; color: black; max-width: 600px; margin: auto;">
        <h1 style="border-bottom: 2px solid #333; padding-bottom: 10px;">🎸 Utlåningskvitto</h1>
        <p style="font-size: 1.1em;"><b>Låntagare:</b> {borrower}</p>
        <p><b>Datum:</b> {date_str}</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <h3 style="margin-bottom: 10px;">Utrustningslista:</h3>
        <ul style="list-style-type: none; padding-left: 0;">{list_items}</ul>
        <div style="margin-top: 40px; font-size: 0.9em; color: #555;">
            <p><i>Hanteras varsamt. Återlämnas i originalskick.</i></p>
            <div style="margin-top: 30px; border-top: 1px solid #000; width: 200px; padding-top: 5px;">Signatur Låntagare</div>
        </div>
        <div style="margin-top: 30px; text-align: center;">
            <button onclick="window.print()" style="padding: 10px 20px; cursor: pointer; background: #000; color: #fff; border: none; border-radius: 5px;">🖨️ Skriv ut packlista</button>
        </div>
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
        st.error("Kunde inte spara till Sheets.")
        return False

st.session_state.df = load_data()

# --- SIDEBAR (KORG OCH NAVIGERING) ---
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
        
    borrower_name = st.sidebar.text_input("Vem lånar? *", key="sb_borrower")
    if borrower_name:
        if st.sidebar.button("Bekräfta utlån ✅", type="primary"):
            today = datetime.now().strftime("%Y-%m-%d")
            st.session_state.last_checkout = {"borrower": borrower_name, "items": list(st.session_state.cart)}
            
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
            
            if save_data(st.session_state.df):
                st.sidebar.success("Utlån registrerat!")
                st.session_state.cart = []
                st.rerun()

if st.session_state.last_checkout:
    with st.sidebar.expander("📄 Skriv ut packlista", expanded=True):
        if st.button("Öppna packlista för utskrift"):
            st.components.v1.html(get_packing_list_html(st.session_state.last_checkout['borrower'], st.session_state.last_checkout['items']), height=500, scrolling=True)
        if st.button("Klar / Dölj"):
            st.session_state.last_checkout = None
            st.rerun()

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    query = st.text_input("Sök (Modell, Märke, Typ, ID)...", placeholder="Skriv här för att filtrera...")
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=90)
                else: st.write("📷")
            with c2:
                status_color = "green" if row['Status'] == 'Tillgänglig' else "red"
                st.markdown(f"### {row['Modell']}")
                st.markdown(f":{status_color}[● {row['Status']}] | {row['Typ']} | ID: {row['Resurstagg']}")
            with c3:
                st.image(generate_qr(row['Resurstagg']), width=60)
            with c4:
                if row['Status'] == 'Tillgänglig':
                    if any(c['Resurstagg'] == row['Resurstagg'] for c in st.session_state.cart):
                        st.success("Ligger i korgen")
                    elif st.button("🛒 Lägg i korg", key=f"cart_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast(f"Tillagd: {row['Modell']}")
                        st.rerun()
                else:
                    st.caption(f"Lånad av: {row['Aktuell ägare']}")
                
                if st.button("✏️ Redigera", key=f"edit_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

    if st.session_state.editing_item is not None:
        st.divider()
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.form("edit_product"):
            st.subheader(f"Redigera {item['Modell']}")
            e_mod = st.text_input("Modell", value=item['Modell'])
            e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
            new_img = st.camera_input("Uppdatera bild")
            if st.form_submit_button("Spara ändringar"):
                st.session_state.df.at[idx, 'Modell'] = e_mod
                st.session_state.df.at[idx, 'Status'] = e_stat
                if new_img: st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_img)
                save_data(st.session_state.df)
                st.session_state.editing_item = None
                st.rerun()
        if st.button("Avbryt redigering"):
            st.session_state.editing_item = None
            st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt objekt")
    
    with st.container(border=True):
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn2:
            if st.button("✨ Generera unikt Serienummer"):
                st.session_state.temp_sn = f"SN-{random.randint(10000, 99999)}"
                st.rerun()

        with st.form("new_product_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                m_in = st.text_input("Modell *")
                t_in = st.text_input("Tillverkare")
                typ_in = st.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Övrigt"])
            with c2:
                # Prioritera genererat nummer
                sn_val = st.session_state.temp_sn if st.session_state.temp_sn else ""
                sn_in = st.text_input("Serienummer / ID *", value=sn_val)
                farg_in = st.text_input("Färg")
            
            foto_in = st.camera_input("Ta foto")
            
            if st.form_submit_button("💾 Spara produkt i lager"):
                if m_in and sn_in:
                    new_id = clean_id(sn_in)
                    new_item = {
                        "Enhetsfoto": process_image_to_base64(foto_in) if foto_in else "",
                        "Modell": m_in, "Tillverkare": t_in, "Typ": typ_in, "Färg": farg_in,
                        "Resurstagg": new_id, "Serienummer": new_id, "Status": "Tillgänglig",
                        "Aktuell ägare": "", "Utlåningsdatum": ""
                    }
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_item])], ignore_index=True)
                    if save_data(st.session_state.df):
                        st.session_state.temp_sn = ""
                        st.success(f"✅ Produkten {m_in} har lagts till!")
                else:
                    st.error("Modell och Serienummer är obligatoriska fält.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Bulk-återlämning")
    active_b = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    
    if len(active_b) > 0:
        target = st.selectbox("Välj person som återlämnar:", ["--- Välj ---"] + list(active_b))
        if target != "--- Välj ---":
            items = st.session_state.df[st.session_state.df['Aktuell ägare'] == target]
            to_return = []
            for i, r in items.iterrows():
                if st.checkbox(f"{r['Modell']} (SN: {r['Serienummer']})", value=True, key=f"ret_{r['Resurstagg']}"):
                    to_return.append(r['Resurstagg'])
            
            if st.button("Bekräfta återlämning", type="primary"):
                for tid in to_return:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                save_data(st.session_state.df)
                st.success("Återlämning klar!")
                st.rerun()
    else:
        st.info("Inga utestående lån just nu.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Administration")
    t1, t2, t3 = st.tabs(["📊 Lagerlista", "🏷️ Bulk-etiketter", "🛠️ Systemlogg"])
    
    with t1:
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]), use_container_width=True)
    
    with t2:
        st.subheader("Massutskrift av etiketter")
        opts = st.session_state.df.apply(lambda r: f"{r['Modell']} | SN:{r['Serienummer']}", axis=1).tolist()
        sel = st.multiselect("Välj produkter att skriva ut:", opts)
        if sel:
            to_p = []
            for o in sel:
                tag = o.split("| SN:")[-1]
                match = st.session_state.df[st.session_state.df['Resurstagg'] == tag]
                if not match.empty: to_p.append(match.iloc[0].to_dict())
            if st.button("Generera etikettark"):
                st.components.v1.html(get_label_html(to_p), height=600, scrolling=True)

    with t3:
        for log in reversed(st.session_state.debug_log): st.text(log)
