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
from io import BytesIO

# --- 1. KONFIGURACJA AI ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priorities = ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "gemini-1.5-flash"]
        for p in priorities:
            if p in available: return genai.GenerativeModel(p)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None

model = get_working_model()

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

def create_excel_in_memory(df_to_save, pil_image=None):
    """Tworzy plik Excel w pamięci RAM i zwraca go jako obiekt BytesIO."""
    output = BytesIO()
    # Zapisujemy dane DataFrame
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_save.to_excel(writer, index=False, sheet_name='Zarobki')
    
    # Jeśli mamy zdjęcie, dopisujemy je za pomocą openpyxl
    if pil_image:
        output.seek(0)
        wb = openpyxl.load_workbook(output)
        ws = wb.active
        row_idx = ws.max_row
        
        img_temp = pil_image.copy()
        img_temp.thumbnail((150, 200))
        img_buffer = BytesIO()
        img_temp.save(img_buffer, format="PNG")
        
        img_to_excel = OpenpyxlImage(img_buffer)
        ws.add_image(img_to_excel, f'I{row_idx}')
        ws.row_dimensions[row_idx].height = 150
        ws.column_dimensions['I'].width = 25
        
        final_output = BytesIO()
        wb.save(final_output)
        return final_output.getvalue()
    
    return output.getvalue()

# --- 3. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.title("📂 Twoje Dane")
    uploaded_file = st.file_uploader("Wgraj swój plik .xlsx (opcjonalnie):", type="xlsx")
    
    st.divider()
    st.header("⚙️ Ustawienia")
    cur_yr = datetime.now().year
    rok = st.selectbox("Rok:", list(range(2024, cur_yr + 11)), index=list(range(2024, cur_yr + 11)).index(cur_yr))
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")
norma_godzin, lista_swiat = get_working_info(rok, m_idx)

tab1, tab2 = st.tabs(["🧮 Rozliczenie", "📊 Historia i Export"])

with tab1:
    with st.expander(f"📅 Norma dla {m_nazwa} {rok}"):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        for s in lista_swiat: st.write(f"• {s}")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        raw_img = Image.open(plik)
        img = ImageOps.exif_transpose(raw_img)
        st.image(img, width=300)
        
        if st.button("🔍 Skanuj AI"):
            with st.spinner("Gemini analizuje grafik..."):
                try:
                    prompt = f"Odczytaj 4. kolumnę (Ilość godzin). Zwróć dane: 1:[wart], 2:[wart]... Użyj 'U' dla urlopów."
                    response = model.generate_content([prompt, img])
                    pairs = re.findall(r"(\d+):\s*([0-9.Uu]+)", response.text)
                    d_list, u_list = [0.0]*31, []
                    for d, v in pairs:
                        d_num = int(d)
                        if d_num <= 31:
                            if v.upper() == 'U': d_list[d_num-1] = 8.0; u_list.append(d_num)
                            else: d_list[d_num-1] = float(v)
                    st.session_state['dni_lista'] = d_list
                    st.session_state['url_dni'] = u_list
                    st.session_state['last_img'] = img
                    st.success("Odczytano!")
                except Exception as e: st.error(f"Błąd AI: {e}")

    if 'dni_lista' in st.session_state:
        num_d = calendar.monthrange(rok, m_idx)[1]
        sel_url = st.multiselect("Urlopy:", range(1, num_d + 1), default=st.session_state.get('url_dni', []))
        
        popr = []
        c_l, c_r = st.columns(2)
        for i in range(num_d):
            with (c_l if i < num_d/2 else c_r):
                d_init = 8.0 if (i+1) in sel_url else st.session_state['dni_lista'][i]
                v = st.number_input(f"Dzień {i+1} ({get_day_name(rok, m_idx, i+1)})", value=float(d_init), step=0.5, key=f"k_{i}")
                popr.append(v)
        
        suma_h = sum(popr)
        nadgodziny = max(0.0, suma_h - norma_godzin)
        total_pln = (suma_h * stawka) + (nadgodziny * dodatek)
        
        st.success(f"### 💰 Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("➕ Przygotuj do zapisu"):
            # Przygotowanie nowego wiersza danych
            new_row = {
                "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
                "Norma": norma_godzin, "Nadgodziny": nadgodziny,
                "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total_pln, 2)
            }
            
            # Wczytanie starej bazy z wgranego pliku
            if uploaded_file:
                df_base = pd.read_excel(uploaded_file)
            else:
                df_base = pd.DataFrame(columns=["Rok", "Miesiąc", "Godziny Suma", "Norma", "Nadgodziny", "Stawka", "Dni Urlopu", "Suma PLN"])
            
            # Usunięcie duplikatu miesiąca i dodanie nowego
            mask = (df_base['Rok'] == rok) & (df_base['Miesiąc'] == m_nazwa)
            df_base = df_base[~mask]
            df_final = pd.concat([df_base, pd.DataFrame([new_row])], ignore_index=True)
            
            # Tworzenie pliku w RAM
            excel_data = create_excel_in_memory(df_final, st.session_state.get('last_img'))
            st.session_state['excel_ready'] = excel_data
            st.success("Plik gotowy! Pobierz go w zakładce 'Historia i Export'.")

with tab2:
    if 'excel_ready' in st.session_state:
        st.download_button(
            label="📥 POBIERZ ZAKTUALIZOWANY ARKUSZ EXCEL",
            data=st.session_state['excel_ready'],
            file_name=f"zarobki_kalkulator_{rok}_{m_nazwa}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif uploaded_file:
        st.info("Wgrałeś plik, ale nie dodałeś jeszcze nowego miesiąca. Dane z Twojego pliku są widoczne poniżej.")
        df_view = pd.read_excel(uploaded_file)
        st.dataframe(df_view)
    else:
        st.info("Tu pojawi się przycisk pobierania po kliknięciu 'Przygotuj do zapisu'.")
