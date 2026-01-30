import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import random
import time

# --- 1. KONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="Musik-IT Birka v7", layout="wide")

if 'cart' not in st.session_state: st.session_state.cart = []
if 'last_loan' not in st.session_state: st.session_state.last_loan = None
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'debug_log' not in st.session_state: st.session_state.debug_log = []

def add_log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.debug_log.append(f"[{ts}] {msg}")

# --- 2. DATAANSLUTNING (SÄKERHETSFOKUS) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_fresh_data():
    """Hämtar alltid färsk data direkt från källan utan cache."""
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        needed_cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                       "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in needed_cols:
            if col not in df.columns: df[col] = ""
        return df.fillna("")
    except Exception as e:
        add_log(f"FETCH ERROR: {e}")
        return pd.DataFrame()

def sync_and_save(df_to_save):
    """Säkerhetsfunktion: Hämtar data igen, slår ihop ändringar och sparar."""
    try:
        if df_to_save is None or df_to_save.empty:
            st.error("Systemet blockerade ett försök att spara tom data.")
            return False
        conn.update(worksheet="Sheet1", data=df_to_save.astype(str))
        st.cache_data.clear()
        add_log("SUCCESS: Data synkad till Sheets.")
        return True
    except Exception as e:
        add_log(f"SAVE ERROR: {e}")
        st.error(f"Kunde inte spara: {e}")
        return False

# Initial laddning
if 'df' not in st.session_state:
    st.session_state.df = get_fresh_data()

# --- 3. HJÄLPFUNKTIONER ---
def generate_id():
    return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

def img_to_b64(file):
    if not file: return ""
    img = Image.open(file)
    img.thumbnail((300, 300))
    buf = BytesIO()
    img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=75)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

def get_qr_b64(data):
    qr = qrcode.make(str(data))
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- 4. SIDEBAR & ADMIN ---
st.sidebar.title("🎸 Musik-IT Birka v7")
pwd = st.sidebar.text_input("Lösenord (Admin)", type="password")
is_admin = (pwd == "Birka")

if st.sidebar.button("🔄 Tvinga omladdning (Cache-flush)"):
    st.session_state.df = get_fresh_data()
    st.rerun()

# --- 5. VARUKORG ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for i, itm in enumerate(st.session_state.cart):
            st.caption(f"{i+1}. {itm['Modell']} ({itm['Resurstagg']})")
        borrower = st.text_input("Låntagare *")
        if st.button("SLUTFÖR UTLÅNING", type="primary"):
            if borrower:
                # SÄKERHET: Hämta nyaste listan precis innan ändring
                current_df = get_fresh_data()
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = current_df[current_df['Resurstagg'] == itm['Resurstagg']].index
                    current_df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
                
                if sync_and_save(current_df):
                    st.session_state.last_loan = {"name": borrower, "date": today, "items": st.session_state.cart.copy()}
                    st.session_state.cart = []
                    st.session_state.df = current_df
                    st.rerun()
            else: st.error("Du måste ange ett namn.")

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- 7. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        st.success("### 📄 Utlåningskvitto")
        l = st.session_state.last_loan
        rows = "".join([f"<li>{i['Modell']} (ID: {i['Resurstagg']})</li>" for i in l['items']])
        receipt_html = f"""
        <div style="border:2px solid #333; padding:15px; font-family:sans-serif;">
            <h2>Musik-IT Birka</h2>
            <p><b>Låntagare:</b> {l['name']}<br><b>Datum:</b> {l['date']}</p>
            <hr><ul>{rows}</ul>
        </div><br><button onclick="window.print()">🖨️ SKRIV UT KVITTO</button>
        """
        st.components.v1.html(receipt_html, height=300)
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    # QR-Kamera
    with st.expander("📷 Skanna QR-kod"):
        st.components.v1.html("""
            <div id="reader" style="width:300px; margin:auto;"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                const scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 200 });
                scanner.render((txt) => { 
                    localStorage.setItem('qr_res', txt);
                    alert("ID Skannat: " + txt);
                });
            </script>
        """, height=350)
        if st.button("Använd skannad kod"):
            st.components.v1.html("""<script>window.parent.location.href = window.parent.location.href.split('?')[0] + '?q=' + localStorage.getItem('qr_res');</script>""", height=0)

    search_query = st.text_input("Sök (Modell, Märke, ID, Färg...)", value=st.query_params.get("q", ""))
    
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)] if search_query else st.session_state.df

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=120)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=70)
            with c2:
                st.subheader(row['Modell'])
                st.caption(f"{row['Tillverkare']} | {row['Typ']} | {row['Färg']}")
                st.write(f"**ID:** {row['Resurstagg']} | **Status:** {row['Status']}")
                if row['Status'] == 'Utlånad': st.error(f"Uthyrd till: {row['Aktuell ägare']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg i vagn", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Editera", key=f"ed_{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

    # EDIT-MODAL
    if is_admin and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        row = st.session_state.df.loc[idx]
        with st.form("edit_form"):
            st.subheader(f"Editera {row['Modell']}")
            c1, c2 = st.columns(2)
            e_mod = c1.text_input("Modell", value=row['Modell'])
            e_brand = c1.text_input("Tillverkare", value=row['Tillverkare'])
            e_status = c2.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], 
                                    index=["Tillgänglig", "Utlånad", "Service", "Trasig"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service", "Trasig"] else 0)
            e_img = st.file_uploader("Byt bild (valfritt)")
            
            del_prod = st.checkbox("RADERA PRODUKT PERMANENT")
            
            if st.form_submit_button("Spara ändringar"):
                current_df = get_fresh_data()
                if del_prod:
                    current_df = current_df.drop(idx).reset_index(drop=True)
                else:
                    current_df.loc[idx, ['Modell', 'Tillverkare', 'Status']] = [e_mod, e_brand, e_status]
                    if e_img: current_df.at[idx, 'Enhetsfoto'] = img_to_b64(e_img)
                
                if sync_and_save(current_df):
                    st.session_state.df = current_df
                    st.session_state.edit_idx = None
                    st.rerun()

# --- 8. NY REGISTRERING (ALLA FÄLT) ---
elif menu == "➕ Ny registrering":
    with st.form("new_reg", clear_on_submit=True):
        st.subheader("Registrera ny utrustning")
        c1, c2 = st.columns(2)
        with c1:
            f_mod = st.text_input("Modell *")
            f_brand = st.text_input("Tillverkare")
            f_typ = st.text_input("Typ")
            f_farg = st.text_input("Färg")
        with c2:
            tag_col, gen_col = st.columns([2,1])
            f_tag = tag_col.text_input("Resurstagg (ID) *", key="f_tag")
            if gen_col.form_submit_button("🔄 ID"):
                f_tag = generate_id()
                st.info(f"Genererat: {f_tag}")
            f_bc = st.text_input("Streckkod")
            f_status = st.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        
        f_foto = st.camera_input("Ta foto")
        
        if st.form_submit_button("✅ SPARA PRODUKT"):
            if f_mod and f_tag:
                current_df = get_fresh_data()
                new_row = {
                    "Modell": f_mod, "Tillverkare": f_brand, "Typ": f_typ, "Färg": f_farg,
                    "Resurstagg": f_tag, "Streckkod": f_bc, "Status": f_status,
                    "Enhetsfoto": img_to_b64(f_foto) if f_foto else "",
                    "Senast inventerad": datetime.now().strftime("%Y-%m-%d"),
                    "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
                if sync_and_save(current_df):
                    st.session_state.df = current_df
                    st.success(f"Sparade {f_mod}!")
            else: st.error("Modell och ID är obligatoriska!")

# --- 9. ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.subheader("Registrera återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    
    # Gruppera efter ägare för att hämta "alla produkter lånade vid samma tillfälle"
    if not borrowed.empty:
        owners = borrowed['Aktuell ägare'].unique()
        sel_owner = st.selectbox("Välj låntagare", owners)
        
        to_return = borrowed[borrowed['Aktuell ägare'] == sel_owner]
        st.write(f"Produkter lånade av **{sel_owner}**:")
        
        for idx, row in to_return.iterrows():
            st.write(f"- {row['Modell']} ({row['Resurstagg']})")
            
        if st.button(f"Återlämna alla från {sel_owner}", type="primary"):
            current_df = get_fresh_data()
            target_indices = current_df[current_df['Aktuell ägare'] == sel_owner].index
            current_df.loc[target_indices, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = \
                ['Tillgänglig', '', '', datetime.now().strftime("%Y-%m-%d")]
            
            if sync_and_save(current_df):
                st.session_state.df = current_df
                st.rerun()
    else: st.info("Inga produkter är utlånade just nu.")

# --- 10. ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    if not is_admin:
        st.warning("Logga in som admin för att se detta läge.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["🖨️ Bulk QR", "📋 Inventering", "📜 Systemlogg", "📊 Rådata"])
        
        with tab1:
            st.write("Skapa etiketter (3x4 cm)")
            sel_qr = st.multiselect("Välj produkter", st.session_state.df['Modell'].tolist())
            if sel_qr:
                html = "<div style='display:flex; flex-wrap:wrap; gap:5px;'>"
                for m in sel_qr:
                    r = st.session_state.df[st.session_state.df['Modell'] == m].iloc[0]
                    qr_b64 = get_qr_b64(r['Resurstagg'])
                    html += f"""
                    <div style="width:3cm; height:4cm; border:1px solid #ccc; text-align:center; padding:5px; font-family:sans-serif;">
                        <img src="data:image/png;base64,{qr_b64}" style="width:2.5cm;"><br>
                        <b style="font-size:10px;">{r['Modell']}</b><br>
                        <small style="font-size:8px;">ID: {r['Resurstagg']}</small>
                    </div>
                    """
                html += "</div><br><button onclick='window.print()'>SKRIV UT ETIKETTER</button>"
                st.components.v1.html(html, height=500, scrolling=True)

        with tab2:
            st.subheader("Inventeringsläge")
            today = datetime.now().strftime("%Y-%m-%d")
            
            inventaried = st.session_state.df[st.session_state.df['Senast inventerad'] == today]
            ej_inventaried = st.session_state.df[st.session_state.df['Senast inventerad'] != today]
            
            col_a, col_b = st.columns(2)
            col_a.metric("Inventerade idag", len(inventaried))
            col_b.metric("Återstår", len(ej_inventaried))
            
            st.write("### Avvikelselista (Ej sedda idag)")
            st.dataframe(ej_inventaried[['Modell', 'Resurstagg', 'Status', 'Aktuell ägare']])
            
            if st.button("Markera alla som inventerade (Varning!)"):
                current_df = get_fresh_data()
                current_df['Senast inventerad'] = today
                sync_and_save(current_df)
                st.rerun()

        with tab3:
            st.subheader("Systemhändelser")
            for log in reversed(st.session_state.debug_log):
                st.text(log)

        with tab4:
            st.dataframe(st.session_state.df)
