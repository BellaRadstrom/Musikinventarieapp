import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64

# --- 1. GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="Musik-IT Birka", layout="wide", page_icon="🎸")

# --- 2. SESSION STATE (Håller reda på allt medan appen körs) ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'auth' not in st.session_state: st.session_state.auth = False
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- 3. FUNKTIONER ---
def clean_id(val):
    if pd.isna(val) or val == "": return ""
    s = str(val).strip()
    return s[:-2] if s.endswith(".0") else s

def img_to_b64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((400, 400))
        buf = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=80)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except: return ""

def generate_qr_b64(data):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- 4. DATAHANTERING (GOOGLE SHEETS) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Tvingar fram en ren läsning utan cache
        data = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in cols:
            if col not in data.columns: data[col] = ""
        data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        st.session_state.df = data.fillna("")
    except Exception as e:
        st.error(f"Kunde inte ansluta till Sheets: {e}")

def save_to_sheets():
    try:
        conn.update(worksheet="Sheet1", data=st.session_state.df.astype(str))
        st.success("✅ Ändringar sparade i Google Sheets!")
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")

if st.session_state.df is None:
    load_data()

# --- 5. LOGIN & ADMIN STATUS ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Lösenord för Admin", type="password")
if pwd == "Birka":
    st.session_state.auth = True
    st.markdown("<div style='background-color:red; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>🔴 ADMIN-LÄGE AKTIVT: Du kan ändra och radera allt</div>", unsafe_allow_html=True)
else:
    st.session_state.auth = False
    st.markdown("<div style='background-color:green; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>🟢 ANVÄNDAR-LÄGE: Sök och låna</div>", unsafe_allow_html=True)

# --- 6. VARUKORG & LÅNEFLÖDE ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 DIN VARUKORG", expanded=True):
        for i, item in enumerate(st.session_state.cart):
            st.write(f"**{i+1}. {item['Modell']}**")
        
        name = st.text_input("Namn på låntagare (Tvingande) *")
        
        if st.button("BEKRÄFTA LÅN", type="primary"):
            if name:
                today = datetime.now().strftime("%Y-%m-%d")
                for c_item in st.session_state.cart:
                    idx = st.session_state.df[st.session_state.df['Resurstagg'] == c_item['Resurstagg']].index
                    st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, today]
                save_to_sheets()
                st.session_state.receipt = {"name": name, "items": st.session_state.cart.copy(), "date": today}
                st.session_state.cart = []
                st.rerun()
            else:
                st.error("Du måste ange ett namn!")
        
        if st.button("Rensa vagn"):
            st.session_state.cart = []
            st.rerun()

# --- 7. HUVUDMENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Nytt", "⚙️ Admin"])

# --- 8. VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # Visa kvitto vid lyckat lån
    if 'receipt' in st.session_state:
        with st.container(border=True):
            st.subheader("✅ Lånebekräftelse")
            st.write(f"**Låntagare:** {st.session_state['receipt']['name']}")
            st.write(f"**Datum:** {st.session_state['receipt']['date']}")
            for itm in st.session_state['receipt']['items']:
                st.write(f"- {itm['Modell']} ({itm['Resurstagg']})")
            st.button("Skriv ut (Ctrl+P)", on_click=lambda: st.write("Använd webbläsarens utskriftsfunktion"))
            if st.button("Stäng kvitto"): 
                del st.session_state.receipt
                st.rerun()

    # Kamerabrygga
    with st.expander("📷 Starta QR-Skanner", expanded=True):
        st.components.v1.html("""
            <div id="reader"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                const scanner = new Html5Qrcode("reader");
                scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, 
                (txt) => { localStorage.setItem('qr', txt); document.getElementById('reader').style.border="5px solid green"; });
            </script>
        """, height=350)
        if st.button("HÄMTA SKANNAD KOD", use_container_width=True):
            st.components.v1.html("""<script>window.parent.location.href = window.parent.location.href.split('?')[0] + '?q=' + localStorage.getItem('qr');</script>""", height=0)

    # Sökning
    q = st.query_params.get("q", "")
    query = st.text_input("Sök i lagret (ID eller namn)", value=q)
    
    if st.session_state.df is not None:
        filtered = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df
        
        for idx, row in filtered.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=120)
                    else: st.write("📷")
                with c2:
                    st.subheader(row['Modell'])
                    st.write(f"**ID:** {row['Resurstagg']} | **Status:** {row['Status']}")
                    if row['Status'] == 'Utlånad': st.error(f"Lånad av: {row['Aktuell ägare']}")
                with c3:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Lägg i vagn", key=f"add_{idx}"):
                            st.session_state.cart.append(row.to_dict())
                            st.rerun()
                    if st.session_state.auth:
                        if st.button("✏️ EDITERA", key=f"edit_{idx}"):
                            st.session_state.edit_idx = idx
                            st.rerun()

# --- 9. VY: EDITERA (ÖPPNAS FRÅN SÖK) ---
if st.session_state.edit_idx is not None:
    idx = st.session_state.edit_idx
    row = st.session_state.df.loc[idx]
    st.divider()
    st.subheader(f"🛠️ Redigerar: {row['Modell']}")
    
    with st.form("edit_form"):
        col1, col2 = st.columns(2)
        with col1:
            m = st.text_input("Modell", value=row['Modell'])
            t = st.text_input("Tillverkare", value=row['Tillverkare'])
            ty = st.text_input("Typ", value=row['Typ'])
            f = st.text_input("Färg", value=row['Färg'])
            rt = st.text_input("Resurstagg (ID)", value=row['Resurstagg'])
        with col2:
            s = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], index=["Tillgänglig", "Utlånad", "Service", "Trasig"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service", "Trasig"] else 0)
            ao = st.text_input("Aktuell ägare", value=row['Aktuell ägare'])
            ud = st.text_input("Utlåningsdatum", value=row['Utlåningsdatum'])
            si = st.text_input("Senast inventerad", value=row['Senast inventerad'])
            new_img = st.file_uploader("Byt bild")
        
        delete_me = st.checkbox("❌ RADERA DENNA PRODUKT PERMANENT")
        
        if st.form_submit_button("SPARA ALLT"):
            if delete_me:
                st.session_state.df = st.session_state.df.drop(idx).reset_index(drop=True)
            else:
                st.session_state.df.loc[idx, ['Modell', 'Tillverkare', 'Typ', 'Färg', 'Resurstagg', 'Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = [m, t, ty, f, rt, s, ao, ud, si]
                if new_img: st.session_state.df.at[idx, 'Enhetsfoto'] = img_to_b64(new_img)
            
            save_to_sheets()
            st.session_state.edit_idx = None
            st.rerun()
    if st.button("Avbryt"):
        st.session_state.edit_idx = None
        st.rerun()

# --- 10. VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Registrera återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if borrowed.empty:
        st.info("Inga prylar är utlånade.")
    else:
        for idx, row in borrowed.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Modell']}** - Lånad av: {row['Aktuell ägare']}")
                if st.button("LÄMNA TILLBAKA", key=f"ret_{idx}"):
                    st.session_state.df.at[idx, 'Status'] = 'Tillgänglig'
                    st.session_state.df.at[idx, 'Aktuell ägare'] = ''
                    st.session_state.df.at[idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d")
                    save_to_sheets()
                    st.rerun()

# --- 11. VY: REGISTRERA ---
elif menu == "➕ Registrera Nytt":
    if not st.session_state.auth: st.warning("Logga in som Admin först.")
    else:
        with st.form("new"):
            m = st.text_input("Modell *")
            i = st.text_input("ID *")
            f = st.camera_input("Ta foto")
            if st.form_submit_button("Spara"):
                new_row = {"Modell": m, "Resurstagg": clean_id(i), "Status": "Tillgänglig", "Enhetsfoto": img_to_b64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_to_sheets()
                st.success("Registrerad!")

# --- 12. VY: ADMIN ---
elif menu == "⚙️ Admin":
    if not st.session_state.auth: st.warning("Logga in.")
    else:
        t1, t2 = st.tabs(["Lagerlista", "Bulk QR"])
        with t1:
            st.dataframe(st.session_state.df)
            if st.button("Tvinga omladdning från Google Sheets"):
                load_data()
                st.rerun()
        with t2:
            st.subheader("Skapa etiketter")
            sel = st.multiselect("Välj prylar:", st.session_state.df['Modell'].tolist())
            if sel:
                html = "<div style='display:flex; flex-wrap:wrap; gap:10px;'>"
                for m_name in sel:
                    row = st.session_state.df[st.session_state.df['Modell'] == m_name].iloc[0]
                    qr = generate_qr_b64(row['Resurstagg'])
                    html += f"<div style='border:1px solid black; padding:5px; width:120px; text-align:center;'><img src='data:image/png;base64,{qr}' style='width:100px;'><br><small>{row['Modell']}</small></div>"
                st.components.v1.html(html + "</div>", height=400, scrolling=True)
