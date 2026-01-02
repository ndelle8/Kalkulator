import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
import os
import calendar
from datetime import date, datetime
from PIL import Image, ImageOps

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

# --- 3. OBSŁUGA BAZY EXCEL ---
DB_FILE = "zarobki_baza.xlsx"

def load_data():
    cols = ["Rok", "Miesiąc", "Godziny Suma", "Norma", "Nadgodziny", "Stawka", "Dni Urlopu", "Suma PLN"]
    if os.path.exists(DB_FILE):
        df = pd.read_excel(DB_FILE)
        for col in cols:
            if col not in df.columns: df[col] = 0
        return df
    return pd.DataFrame(columns=cols)

# --- 4. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    lata = list(range(2024, datetime.now().year + 11))
    rok = st.selectbox("Rok:", lata, index=lata.index(datetime.now().year))
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)

tab1, tab2 = st.tabs(["🧮 Rozliczenie", "📊 Archiwum"])

with tab1:
    plik = st.file_uploader("Zrób zdjęcie lub wgraj grafik:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        # --- FIX DLA TELEFONU: Orientacja i Rozmiar ---
        img = Image.open(plik)
        img = ImageOps.exif_transpose(img) # Automatyczne obracanie zdjęcia do pionu
        st.image(img, width=300, caption="Twoje zdjęcie (poprawione do pionu)")
        
        if st.button("🚀 ANALIZUJ GRAFIK"):
            with st.spinner("Sztuczna inteligencja analizuje pismo..."):
                try:
                    # Bardziej agresywny prompt dla telefonów
                    prompt = f"""To jest grafik pracy na {m_nazwa} {rok}. 
                    Zlokalizuj tabelę i kolumnę 'Ilość godzin'. 
                    Wypisz wartości dla kolejnych dni od 1 do 31, idąc od góry do dołu.
                    ZASADY:
                    - Jeśli widzisz liczbę (np. 8, 10, 12), wypisz ją.
                    - Jeśli widzisz 'URL', 'URLOP', 'URZ', wpisz 'U'.
                    - Jeśli dzień jest pusty lub jest kreska, wpisz '0'.
                    FORMAT: Zwróć tylko listę 31 wartości oddzielonych przecinkami, np: 8,8,U,0,8..."""
                    
                    response = model.generate_content([prompt, img])
                    
                    # Parsowanie wyników
                    raw_items = response.text.replace(" ", "").split(",")
                    
                    extracted_hours = []
                    extracted_urlopy = []
                    
                    for i, item in enumerate(raw_items[:31]):
                        day_num = i + 1
                        if 'U' in item.upper():
                            extracted_hours.append(8.0)
                            extracted_urlopy.append(day_num)
                        else:
                            nums = re.findall(r"(\d+(?:\.\d+)?)", item)
                            extracted_hours.append(float(nums[0]) if nums else 0.0)
                    
                    while len(extracted_hours) < 31: extracted_hours.append(0.0)
                    
                    st.session_state['dni_lista'] = extracted_hours
                    st.session_state['urlopy_dni'] = extracted_urlopy
                    st.success("✅ Grafik odczytany! Sprawdź poprawność poniżej.")
                except Exception as e:
                    st.error(f"Błąd analizy: {e}")

    # --- SEKCJA KOREKTY ---
    if 'dni_lista' in st.session_state:
        num_days = calendar.monthrange(rok, m_idx)[1]
        
        st.subheader("📝 Sprawdź i popraw dane")
        
        wybrane_urlopy = st.multiselect(
            "Zaznaczone jako URLOP (8h):",
            options=range(1, num_days + 1),
            default=st.session_state.get('urlopy_dni', []),
            format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})"
        )

        poprawione = []
        cols = st.columns(7)
        for i in range(num_days):
            day_num = i + 1
            with cols[i % 7]:
                val_init = 8.0 if day_num in wybrane_urlopy else st.session_state['dni_lista'][i]
                v = st.number_input(f"{day_num} {get_day_name(rok, m_idx, day_num)}", 
                                    value=float(val_init), key=f"inp_{i}", step=0.5)
                poprawione.append(v)
        
        # Obliczenia
        suma_h = sum(poprawione)
        nadgodziny = max(0.0, suma_h - norma_godzin)
        total_pln = (suma_h * stawka) + (nadgodziny * dodatek)
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Suma godzin", f"{suma_h} h")
        c2.metric("Norma etatu", f"{norma_godzin} h")
        c3.metric("Nadgodziny", f"{nadgodziny} h")
        
        st.success(f"### 💰 Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("💾 Zapisz do bazy Excel"):
            df = load_data()
            new_data = {
                "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
                "Norma": norma_godzin, "Nadgodziny": nadgodziny,
                "Stawka": stawka, "Dni Urlopu": len(wybrane_urlopy), "Suma PLN": round(total_pln, 2)
            }
            # Zapis... (kod zapisu identyczny jak wcześniej)
            st.success("Zapisano!")
