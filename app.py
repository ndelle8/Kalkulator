import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
from datetime import date, datetime
import calendar
from PIL import Image

# --- 1. KONFIGURACJA AI Z AUTO-WYKRYWANIEM ---
@st.cache_resource
def get_working_model():
    """Wyszukuje dostępny model Gemini, aby uniknąć błędu 404."""
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Pobieramy listę wszystkich dostępnych modeli dla Twojego klucza
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Szukamy modelu Flash 1.5 w różnych wariantach
        priorities = ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "gemini-1.5-flash"]
        for p in priorities:
            if p in available: return genai.GenerativeModel(p)
            
        # Jeśli nie ma 1.5, bierzemy jakikolwiek dostępny model Flash
        fallback = [m for m in available if "flash" in m]
        if fallback: return genai.GenerativeModel(fallback[0])
        
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Nie udało się połączyć z Google AI: {e}")
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

# --- 3. INTERFEJS ---
st.set_page_config(page_title="Kalkulator Zarobków 2026", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    rok = st.selectbox("Rok:", [2025, 2026], index=1)
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    # Zmiana domyślnego dodatku na 15 zł
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("🚀 AI Kalkulator Zarobków (Bilans Miesięczny)")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)

tab1, tab2 = st.tabs(["🧮 Rozliczenie", "📊 Historia"])

with tab1:
    with st.expander(f"📅 Norma i święta: {m_nazwa} {rok}", expanded=False):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            for s in lista_swiat: st.write(f"• {s}")
        else: st.write("Brak świąt w dni robocze.")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=350)
        if st.button("🔍 Analizuj grafik"):
            if model:
                with st.spinner("Gemini czyta pismo odręczne..."):
                    try:
                        prompt = "Znajdź kolumnę 'Ilość godzin'. Podaj TYLKO 31 liczb oddzielonych przecinkami (dla dni 1-31). Dni wolne = 0."
                        response = model.generate_content([prompt, img])
                        numbers = re.findall(r"(\d+(?:\.\d+)?)", response.text)
                        parsed = [float(x) for x in numbers]
                        while len(parsed) < 31: parsed.append(0.0)
                        st.session_state['dni_lista'] = parsed[:31]
                        st.success("✅ Odczytano!")
                    except Exception as e: st.error(f"Błąd analizy: {e}")
            else: st.error("Silnik AI nie jest gotowy. Sprawdź GOOGLE_API_KEY w Secrets.")

    if 'dni_lista' in st.session_state:
        st.subheader("📝 Korekta godzin")
        poprawione = []
        cols = st.columns(7)
        num_days_in_month = calendar.monthrange(rok, m_idx)[1]

        for i in range(num_days_in_month):
            day_name = get_day_name(rok, m_idx, i + 1)
            with cols[i % 7]:
                val = st.number_input(f"{i+1} {day_name}", value=st.session_state['dni_lista'][i], key=f"d_{i}", step=0.5)
                poprawione.append(val)
        
        # --- LOGIKA BILANSOWA ---
        suma_wszystkich = sum(poprawione)
        nadgodziny_bilans = max(0.0, suma_wszystkich - norma_godzin)
        
        # Wypłata: Wszystkie godziny * stawka + (nadwyżka * dodatek)
        total_pln = (suma_wszystkich * stawka) + (nadgodziny_bilans * dodatek)
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Suma przepracowana", f"{suma_wszystkich} h")
        c2.metric("Norma etatu", f"{norma_godzin} h")
        c3.metric("Nadgodziny (Bilans)", f"{nadgodziny_bilans} h", delta=f"+{nadgodziny_bilans}" if nadgodziny_bilans > 0 else None)
        
        st.success(f"### 💰 Wypłata do wypłacenia: **{total_pln:,.2f} zł brutto**")
        
        with st.expander("Szczegóły wyliczenia"):
            st.write(f"• Podstawa za wszystkie godziny: {suma_wszystkich} h × {stawka} zł = {suma_wszystkich * stawka:,.2f} zł")
            if nadgodziny_bilans > 0:
                st.write(f"• Dodatek za nadpracowane godziny: {nadgodziny_bilans} h × {dodatek} zł = {nadgodziny_bilans * dodatek:,.2f} zł")
            st.info("System rozlicza Cię w skali miesiąca. Każda godzina powyżej normy miesięcznej jest liczona z dodatkiem.")
