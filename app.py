import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
import calendar
from datetime import date, datetime
from PIL import Image, ImageOps
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.chart import BarChart, Reference
from io import BytesIO

# --- 1. DYNAMICZNA KONFIGURACJA AI ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Szukamy modelu Flash (najwyższe limity darmowe)
        target_models = [
            "models/gemini-1.5-flash-8b", 
            "models/gemini-1.5-flash",
            "models/gemini-2.0-flash-exp"
        ]
        
        for target in target_models:
            if target in available:
                return genai.GenerativeModel(target), target
        
        fallback = [m for m in available if "flash" in m]
        if fallback:
            return genai.GenerativeModel(fallback[0]), fallback[0]
            
        return None, "Brak połączenia"
    except Exception as e:
        return None, f"Błąd: {str(e)}"

model, active_model_name = get_working_model()

# --- 2. FUNKCJE POMOCNICZE ---
M_LIST = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

def get_working_info(year, month):
    pl_hols = holidays.Poland(years=year)
    num_days = calendar.monthrange(year, month)[1]
    working_days = 0
    holiday_list = []
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date in pl_hols and curr_date.weekday() < 5:
            holiday_list.append(f"{day} {M_LIST[month-1]} - {pl_hols.get(curr_date)}")
        if curr_date.weekday() < 5 and curr_date not in pl_hols:
            working_days += 1
    return working_days * 8, holiday_list

def get_day_name(year, month, day):
    dni = ["Pon", "Wto", "Śro", "Czw", "Pią", "Sob", "Nie"]
    try: return dni[date(year, month, day).weekday()]
    except: return ""

def create_excel_with_stats(df_final, pil_image=None):
    # Sortowanie chronologiczne
    df_final['M_Idx'] = df_final['Miesiąc'].apply(lambda x: M_LIST.index(x))
    df_final = df_final.sort_values(['Rok', 'M_Idx']).drop(columns=['M_Idx'])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Zarobki')
        stats_df = df_final[['Miesiąc', 'Godziny Suma', 'Nadgodziny', 'Suma PLN']]
        stats_df.to_excel(writer, index=False, sheet_name='Statystyki')

    output.seek(0)
    wb = openpyxl.load_workbook(output)
    
    # Arkusz Zarobki (Zdjęcie/Miniaturka)
    ws1 = wb['Zarobki']
    if pil_image:
        row_idx = ws1.max_row
        img_temp = pil_image.copy()
        img_temp.thumbnail((1600, 2000))
        img_buf = BytesIO()
        img_temp.save(img_buf, format="PNG")
        img_xl = OpenpyxlImage(img_buf)
        img_xl.width, img_xl.height = 80, 105
        ws1.add_image(img_xl, f'I{row_idx}')
        ws1.row_dimensions[row_idx].height = 80
        ws1.column_dimensions['I'].width = 15

    # Arkusz Statystyki (Wykresy) - TUTAJ BYŁ BŁĄD SKŁADNI
    ws2 = wb['Statystyki']
    max_row = ws2.max_row
    
    if max_row > 1:
        # 1. Wykres Godzin (Kolumna B = 2)
        c1 = BarChart()
        c1.title = "Suma Godzin"
        d1 = Reference(ws2, min_col=2, min_row=1, max_row=max_row)
        cats = Reference(ws2, min_col=1, min_row=2, max_row=max_row)
        c1.add_data(d1, titles_from_data=True)
        c1.set_categories(cats)
        ws2.add_chart(c1, "F2")

        # 2. Wykres Nadgodzin (Kolumna C = 3)
        c2 = BarChart()
        c2.title = "Nadgodziny"
        d2 = Reference(ws2, min_col=3, min_row=1, max_row=max_row)
        c2.add_data(d2, titles_from_data=True)
        c2.set_categories(cats)
        ws2.add_chart(c2, "F17")

        # 3. Wykres Zarobków (Kolumna D = 4)
        c3 = BarChart()
        c3.title = "Zarobki PLN"
        d3 = Reference(ws2, min_col=4, min_row=1, max_row=max_row)
        c3.add_data(d3, titles_from_data=True)
        c3.set_categories(cats)
        ws2.add_chart(c3, "F32")

    final_out = BytesIO()
    wb.save(final_out)
    return final_out.getvalue()

# --- 3. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.title("📂 Zarządzanie")
    uploaded_file = st.file_uploader("Wgraj swój plik Excel (.xlsx):", type="xlsx")
    st.divider()
    st.header("⚙️ Ustawienia")
    cur_yr = datetime.now().year
    rok = st.selectbox("Rok:", list(range(2024, cur_yr + 11)), index=list(range(2024, cur_yr + 11)).index(cur_yr))
    m_nazwa = st.selectbox("Miesiąc:", M_LIST, index=datetime.now().month-1)
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")
if active_model_name:
    st.caption(f"🤖 Aktywny silnik AI: `{active_model_name}`")

# Norma godzin
m_idx = M_LIST.index(m_nazwa) + 1
norma_h, swieta = get_working_info(rok, m_idx)

with st.expander(f"📅 Norma dla {m_nazwa} {rok}", expanded=False):
    st.write(f"Wymiar czasu pracy: **{norma_h} h**")
    for s in swieta: st.write(f"• {s}")

plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])

if plik:
    img = ImageOps.exif_transpose(Image.open(plik))
    st.image(img, width=300)
    
    if st.button("🔍 ANALIZUJ GRAFIK PRZEZ AI"):
        if model:
            with st.spinner("Sztuczna inteligencja analizuje dane..."):
                try:
                    prompt = "Odczytaj kolumnę 'Ilość godzin' dla dni 1-31. Format: 1: [wart], 2: [wart]... 'U' dla urlopów."
                    response = model.generate_content([prompt, img])
                    pairs = re.findall(r"(\d+):\s*([0-9.Uu]+)", response.text)
                    
                    d_list = [0.0]*31
                    u_list = []
                    for d, v in pairs:
                        dn = int(d)
                        if dn <= 31:
                            if v.upper() == 'U':
                                d_list[dn-1] = 8.0
                                u_list.append(dn)
                            else:
                                try: d_list[dn-1] = float(v)
                                except: pass
                    st.session_state['dni_lista'] = d_list
                    st.session_state['url_dni'] = u_list
                    st.session_state['last_img'] = img
                    st.success("✅ Grafik odczytany pomyślnie!")
                except Exception as e:
                    st.error(f"Błąd AI: {e}")

# Korekta i wyniki
if 'dni_lista' in st.session_state:
    st.divider()
    num_d = calendar.monthrange(rok, m_idx)[1]
    st.subheader("📝 Korekta godzin")
    
    sel_url = st.multiselect("Zaznacz dni urlopowe (8h):", range(1, num_d + 1), 
                             default=st.session_state.get('url_dni', []),
                             format_
