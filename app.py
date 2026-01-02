import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
import os
import calendar
from datetime import date, datetime
from PIL import Image, ImageOps
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from io import BytesIO

# --- 1. KONFIGURACJA AI ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priorities = ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "gemini-1.5-flash"]
        for p in priorities:
            if p in available: return genai.GenerativeModel(p), p
        return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash'
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None, None

model, active_model_name = get_working_model()

# --- 2. FUNKCJE POMOCNICZE ---
def get_working_info(year, month):
    pl_hols = holidays.Poland(years=year)
    working_days = 0
    holiday_list = []
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date in pl_hols and curr_date.weekday() < 5:
            holiday_list.append(f"{day} {calendar.month_name[month]} - {pl_hols.get(curr_date)}")
        if curr_date.weekday() < 5 and curr_date not in pl_hols:
            working_days += 1
    return working_days * 8, holiday_list

def get_day_name(year, month, day):
    dni = ["Pon", "Wto", "Śro", "Czw", "Pią", "Sob", "Nie"]
    try: return dni[date(year, month, day).weekday()]
    except: return ""

# --- 3. OBSŁUGA BAZY EXCEL ZE ZDJĘCIAMI ---
DB_FILE = "zarobki_baza.xlsx"

def load_data():
    if os.path.exists(DB_FILE):
        try: return pd.read_excel(DB_FILE)
        except: return pd.DataFrame()
    return pd.DataFrame()

def save_to_excel_with_image(new_data, pil_image):
    # 1. Przygotowanie danych (Pandas)
    df = load_data()
    # Usuwamy stary wpis dla tego samego miesiąca/roku jeśli istnieje
    if not df.empty:
        mask = (df['Rok'] == new_data['Rok']) & (df['Miesiąc'] == new_data['Miesiąc'])
        df = df[~mask]
    
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_excel(DB_FILE, index=False)
    
    # 2. Wstawianie zdjęcia (Openpyxl)
    wb = openpyxl.load_workbook(DB_FILE)
    ws = wb.active
    
    # Znajdujemy wiersz, w którym właśnie zapisaliśmy dane
    row_idx = ws.max_row
    
    # Zapisujemy miniaturkę do tymczasowego bufora
    img_temp = pil_image.copy()
    img_temp.thumbnail((150, 200)) # Skalowanie zdjęcia do Excela
    img_buffer = BytesIO()
    img_temp.save(img_buffer, format="PNG")
    
    # Wstawiamy zdjęcie do kolumny I (9-ta kolumna)
    img_to_excel = OpenpyxlImage(img_buffer)
    ws.add_image(img_to_excel, f'I{row_idx}')
    
    # Ustawienie wysokości wiersza, by zdjęcie się zmieściło
    ws.row_dimensions[row_idx].height = 150
    ws.column_dimensions['I'].width = 25
    
    wb.save(DB_FILE)

# --- 4. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    # Dynamiczna lista lat
    cur_yr = datetime.now().year
    lata = list(range(2024, cur_yr + 11))
    rok = st.selectbox("Rok:", lata, index=lata.index(cur_yr))
    
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)
    
    st.divider()
    st.write("📂 **Zarządzanie bazą**")
    uploaded_db = st.file_uploader("Wgraj swoją bazę (.xlsx), aby dopisać dane:", type="xlsx")
    if uploaded_db:
        with open(DB_FILE, "wb") as f:
            f.write(uploaded_db.getbuffer())
        st.success("Baza załadowana!")

st.title("Kalkulator czasu pracy")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)
tab1, tab2 = st.tabs(["🧮 Rozliczenie", "📊 Archiwum"])

with tab1:
    plik = st.file_uploader("Zrób zdjęcie lub wgraj grafik:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        raw_img = Image.open(plik)
        img = ImageOps.exif_transpose(raw_img) # Fix orientacji z telefonu
        st.image(img, width=300)
        
        if st.button("🚀 ANALIZUJ GRAFIK"):
            if model:
                with st.spinner("AI analizuje grafik..."):
                    try:
                        prompt = f"""To jest grafik na {m_nazwa} {rok}. Odczytaj 4. kolumnę (Ilość godzin). 
                        Zwróć dane DOKŁADNIE w formacie: 1:[wartość], 2:[wartość], ..., 31:[wartość].
                        Używaj 'U' dla urlopów i '0' dla wolnego."""
                        response = model.generate_content([prompt, img])
                        pairs = re.findall(r"(\d+):\s*([0-9.Uu]+)", response.text)
                        
                        d_list, u_list = [0.0]*31, []
                        for d, v in pairs:
                            d_num = int(d)
                            if d_num <= 31:
                                if v.upper() == 'U':
                                    d_list[d_num-1] = 8.0
                                    u_list.append(d_num)
                                else:
                                    try: d_list[d_num-1] = float(v)
                                    except: pass
                        st.session_state['dni_lista'] = d_list
                        st.session_state['url_dni'] = u_list
                        st.session_state['last_img'] = img # Zapamiętujemy zdjęcie do zapisu
                        st.success("Odczytano!")
                    except Exception as e: st.error(f"Błąd AI: {e}")

    if 'dni_lista' in st.session_state:
        num_d = calendar.monthrange(rok, m_idx)[1]
        st.subheader("📝 Korekta godzin")
        
        sel_url = st.multiselect("Dni urlopowe (8h):", range(1, num_d + 1), 
                                 default=st.session_state.get('url_dni', []),
                                 format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})")

        popr = []
        c_l, c_r = st.columns(2)
        for i in range(num_d):
            d_n = i + 1
            with (c_l if i < num_d/2 else c_r):
                d_init = 8.0 if d_n in sel_url else st.session_state['dni_lista'][i]
                v = st.number_input(f"Dzień {d_n} ({get_day_name(rok, m_idx, d_n)})", 
                                    value=float(d_init), key=f"k_{i}", step=0.5)
                popr.append(v)
        
        suma_h = sum(popr)
        nadgodziny = max(0.0, suma_h - norma_godzin)
        total_pln = (suma_h * stawka) + (nadgodziny * dodatek)
        
        st.divider()
        st.success(f"### 💰 Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("💾 Zapisz do historii (razem ze zdjęciem)"):
            save_to_excel_with_image({
                "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
                "Norma": norma_godzin, "Nadgodziny": nadgodziny,
                "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total_pln, 2)
            }, st.session_state['last_img'])
            st.balloons()
            st.success("Zapisano w arkuszu!")

with tab2:
    df_db = load_data()
    if not df_db.empty:
        df_rok = df_db[df_db['Rok'] == rok].copy()
        if not df_rok.empty:
            st.subheader(f"Zestawienie za rok {rok}")
            st.bar_chart(df_rok, x="Miesiąc", y="Suma PLN")
            st.dataframe(df_rok, use_container_width=True)
            with open(DB_FILE, "rb") as f:
                st.download_button("📥 Pobierz arkusz Excel ze zdjęciami", data=f, file_name=f"zarobki_{rok}.xlsx")
    else: st.info("Baza danych jest pusta.")
