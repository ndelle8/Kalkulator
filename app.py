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

# --- 1. KONFIGURACJA AI (ZABEZPIECZONA) ---
@st.cache_resource
def get_working_model():
    try:
        if "GOOGLE_API_KEY" not in st.secrets:
            return None, "Brak klucza API w Secrets!"
        
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # Pobieranie listy modeli
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Wybór stabilnego modelu
        for target in ["models/gemini-1.5-flash-8b", "models/gemini-1.5-flash"]:
            if target in available:
                return genai.GenerativeModel(target), target
        
        if available:
            return genai.GenerativeModel(available[0]), available[0]
        
        return None, "Nie znaleziono obsługiwanych modeli na Twoim koncie."
    except Exception as e:
        return None, f"Błąd inicjalizacji: {str(e)}"

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

def process_excel_save(uploaded_file, new_data, pil_image):
    """Zapisuje dane do Excela, zachowując istniejące obrazy i statystyki."""
    if uploaded_file:
        wb = openpyxl.load_workbook(BytesIO(uploaded_file.read()))
    else:
        wb = openpyxl.Workbook()
        wb.active.title = "Zarobki"
        ws = wb.active
        ws.append(["Rok", "Miesiąc", "Godziny Suma", "Norma", "Nadgodziny", "Stawka", "Dni Urlopu", "Suma PLN", "Grafik"])

    ws = wb["Zarobki"]
    
    # Szukanie wiersza do aktualizacji
    target_row = ws.max_row + 1
    for row in range(2, ws.max_row + 1):
        if str(ws.cell(row, 1).value) == str(new_data["Rok"]) and str(ws.cell(row, 2).value) == str(new_data["Miesiąc"]):
            target_row = row
            break
    
    # Zapis danych
    ws.cell(target_row, 1, new_data["Rok"])
    ws.cell(target_row, 2, new_data["Miesiąc"])
    ws.cell(target_row, 3, new_data["Godziny Suma"])
    ws.cell(target_row, 4, new_data["Norma"])
    ws.cell(target_row, 5, new_data["Nadgodziny"])
    ws.cell(target_row, 6, new_data["Stawka"])
    ws.cell(target_row, 7, new_data["Dni Urlopu"])
    ws.cell(target_row, 8, new_data["Suma PLN"])

    if pil_image:
        img_temp = pil_image.copy()
        img_temp.thumbnail((1600, 2000))
        img_buf = BytesIO()
        img_temp.save(img_buf, format="PNG")
        img_xl = OpenpyxlImage(img_buf)
        img_xl.width, img_xl.height = 80, 105
        ws.add_image(img_xl, f'I{target_row}')
        ws.row_dimensions[target_row].height = 80
        ws.column_dimensions['I'].width = 15

    # Statystyki
    if "Statystyki" in wb.sheetnames: del wb["Statystyki"]
    ws_s = wb.create_sheet("Statystyki")
    ws_s.append(['Miesiąc', 'Godziny Suma', 'Nadgodziny', 'Suma PLN'])
    
    # Pobieranie danych do wykresów (chronologicznie)
    rows_data = []
    for r in range(2, ws.max_row + 1):
        m_val = ws.cell(r, 2).value
        if m_val in M_LIST:
            rows_data.append([ws.cell(r, 1).value, m_val, ws.cell(r, 3).value, ws.cell(r, 5).value, ws.cell(r, 8).value])
    
    df_tmp = pd.DataFrame(rows_data, columns=['Rok', 'Miesiąc', 'Godziny', 'Nadgodziny', 'PLN'])
    df_tmp['M_Idx'] = df_tmp['Miesiąc'].apply(lambda x: M_LIST.index(x))
    df_tmp = df_tmp.sort_values(['Rok', 'M_Idx'])
    
    for r in df_tmp[['Miesiąc', 'Godziny', 'Nadgodziny', 'PLN']].values:
        ws_s.append(list(r))

    # Wykresy
    if ws_s.max_row > 1:
        for i, title in enumerate(["Suma Godzin", "Nadgodziny", "Zarobki PLN"], 2):
            chart = BarChart()
            chart.title = title
            chart.add_data(Reference(ws_s, min_col=i, min_row=1, max_row=ws_s.max_row), titles_from_data=True)
            chart.set_categories(Reference(ws_s, min_col=1, min_row=2, max_row=ws_s.max_row))
            ws_s.add_chart(chart, f"F{2 + (i-2)*15}")

    out = BytesIO()
    wb.save(out)
    return out.getvalue()

# --- 3. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.title("📂 Zarządzanie")
    uploaded_file = st.file_uploader("Wgraj bazę .xlsx:", type="xlsx")
    st.divider()
    st.header("⚙️ Ustawienia")
    cur_y = datetime.now().year
    rok = st.selectbox("Rok:", list(range(2024, cur_y+11)), index=list(range(2024, cur_y+11)).index(cur_y))
    m_nazwa = st.selectbox("Miesiąc:", M_LIST, index=datetime.now().month-1)
    stawka = st.number_input("Stawka (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")
if model:
    st.caption(f"✅ AI Gotowe: `{active_model_name}`")
else:
    st.error(f"❌ AI Nieaktywne: {active_model_name}")

m_idx = M_LIST.index(m_nazwa) + 1
norma_h, swieta = get_working_info(rok, m_idx)

with st.expander(f"📅 Norma dla {m_nazwa} {rok}"):
    st.write(f"Wymiar: **{norma_h} h**")
    for s in swieta: st.write(f"• {s}")

plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])

if plik:
    img = ImageOps.exif_transpose(Image.open(plik))
    st.image(img, width=300)
    
    if st.button("🚀 SKANUJ GRAFIK"):
        if model:
            with st.spinner("AI analizuje grafik..."):
                try:
                    prompt = "Odczytaj kolumnę 'Ilość godzin' dla dni 1-31. Format: 1: [wart], 2: [wart]... ZASADA: 'x', 'X', '-' to 0. 'URL' to U."
                    response = model.generate_content([prompt, img])
                    pairs = re.findall(r"(\d+):\s*([0-9.UuXx-]+)", response.text)
                    d_list = [0.0]*31
                    u_list = []
                    for d, v in pairs:
                        dn = int(d)
                        if dn <= 31:
                            val = v.upper().strip()
                            if 'U' in val: d_list[dn-1] = 8.0; u_list.append(dn)
                            elif val in ['X', '-', '']: d_list[dn-1] = 0.0
                            else:
                                try: d_list[dn-1] = float(re.findall(r"(\d+(?:\.\d+)?)", val)[0])
                                except: pass
                    st.session_state['dni_lista'] = d_list
                    st.session_state['url_dni'] = u_list
                    st.session_state['last_img'] = img
                    st.success("✅ Odczytano!")
                except Exception as e: st.error(f"Błąd AI: {e}")
        else:
            st.error("Nie można skanować: AI nie jest skonfigurowane.")

if 'dni_lista' in st.session_state:
    st.divider()
    num_d = calendar.monthrange(rok, m_idx)[1]
    st.subheader("📝 Korekta i wyniki")
    
    sel_url = st.multiselect("Urlopy (8h):", range(1, num_d + 1), default=st.session_state.get('url_dni', []), format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})")

    popr = []
    c_l, c_r = st.columns(2)
    for i in range(num_d):
        dn = i + 1
        with (c_l if i < num_d/2 else c_r):
            d_init = 8.0 if dn in sel_url else st.session_state['dni_lista'][i]
            v = st.number_input(f"Dz {dn} ({get_day_name(rok, m_idx, dn)})", value=float(d_init), step=0.5, key=f"d_{i}")
            popr.append(v)
    
    suma_h = sum(popr)
    nadgodziny = max(0.0, suma_h - norma_h)
    total = (suma_h * stawka) + (nadgodziny * dodatek)
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Suma godzin", f"{suma_h} h")
    col2.metric("Nadgodziny", f"{nadgodziny} h")
    col3.metric("Wypłata BRUTTO", f"{total:,.2f} zł")
    st.divider()

    if st.button("📊 Zapisz i przygotuj plik Excel"):
        excel_data = process_excel_save(uploaded_file, {
            "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
            "Norma": norma_h, "Nadgodziny": nadgodziny,
            "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total, 2)
        }, st.session_state.get('last_img'))
        st.session_state['excel_ready'] = excel_data
        st.success("✅ Plik zaktualizowany!")

    if 'excel_ready' in st.session_state:
        st.download_button("📥 POBIERZ PLIK EXCEL", data=st.session_state['excel_ready'], file_name=f"zarobki_{rok}_{m_nazwa}.xlsx")
