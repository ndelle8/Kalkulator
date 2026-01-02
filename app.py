import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
import os
import calendar
from datetime import date, datetime
from PIL import Image

# --- 1. KONFIGURACJA AI ---
@st.cache_resource
def get_working_model():
    """Automatyczne wykrywanie dostępnego modelu Gemini, aby uniknąć błędów 404."""
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priorities = ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "gemini-1.5-flash"]
        for p in priorities:
            if p in available: return genai.GenerativeModel(p), p
        fallback = [m for m in available if "flash" in m]
        if fallback: return genai.GenerativeModel(fallback[0]), fallback[0]
        return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash'
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None, None

model, model_name = get_working_model()

# --- 2. FUNKCJE POMOCNICZE ---
def get_working_info(year, month):
    """Zwraca normę godzin dla miesiąca oraz listę świąt."""
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
    """Zwraca skrót dnia tygodnia."""
    dni = ["Pon", "Wto", "Śro", "Czw", "Pią", "Sob", "Nie"]
    try: return dni[date(year, month, day).weekday()]
    except: return ""

# --- 3. OBSŁUGA BAZY EXCEL ---
DB_FILE = "zarobki_baza.xlsx"

def load_data():
    """Wczytuje historię z pliku Excel."""
    cols = ["Rok", "Miesiąc", "Godziny Suma", "Norma", "Nadgodziny", "Stawka", "Dni Urlopu", "Suma PLN"]
    if os.path.exists(DB_FILE):
        df = pd.read_excel(DB_FILE)
        for col in cols:
            if col not in df.columns: df[col] = 0
        return df
    return pd.DataFrame(columns=cols)

def save_to_excel(new_data):
    """Zapisuje lub aktualizuje miesiąc w pliku Excel."""
    df = load_data()
    mask = (df['Rok'] == new_data['Rok']) & (df['Miesiąc'] == new_data['Miesiąc'])
    if any(mask): df = df[~mask]
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_excel(DB_FILE, index=False)
    return df

# --- 4. INTERFEJS UŻYTKOWNIKA ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    # Dynamiczna lista lat: od 2024 do 10 lat w przód
    current_year = datetime.now().year
    lata = list(range(2024, current_year + 11))
    rok = st.selectbox("Rok:", lata, index=lata.index(current_year))
    
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    # Standardowy dodatek zmieniony na 15 zł
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)
tab1, tab2 = st.tabs(["🧮 Rozliczenie i Skanowanie", "📊 Archiwum i Statystyki"])

with tab1:
    with st.expander(f"📅 Norma i informacje: {m_nazwa} {rok}"):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            for s in lista_swiat: st.write(f"• {s}")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=300)
        if st.button("🔍 Skanuj grafik przez AI"):
            if model:
                with st.spinner("Gemini analizuje pismo odręczne i szuka urlopów..."):
                    try:
                        prompt = """Odczytaj 4. kolumnę (Ilość godzin). Zwróć 3
