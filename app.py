import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
from datetime import date, datetime
import calendar
from PIL import Image

# --- 1. KONFIGURACJA AI ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Problem z konfiguracją Google AI: {e}")

# --- 2. FUNKCJE POMOCNICZE ---
def get_working_info(year, month):
    """Zwraca normę godzin oraz listę świąt (bez weekendów)."""
    pl_hols = holidays.Poland(years=year)
    working_days = 0
    holiday_list = []
    num_days = calendar.monthrange(year, month)[1]
    
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        # Sprawdzamy czy to święto
        if curr_date in pl_hols:
            # Jeśli święto wypada w dzień roboczy (Pn-Pt), dodajemy do listy
            if curr_date.weekday() < 5:
                holiday_list.append(f"{day} {calendar.month_name[month]} - {pl_hols.get(curr_date)}")
        
        # Liczymy dni robocze (Pn-Pt i nie święto)
        if curr_date.weekday() < 5 and curr_date not in pl_hols:
            working_days += 1
            
    return working_days * 8, holiday_list

def get_day_name(year, month, day):
    """Zwraca skrót dnia tygodnia po polsku."""
    dni = ["Pon", "Wto", "Śro", "Czw", "Pią", "Sob", "Nie"]
    try:
        idx = date(year, month, day).weekday()
        return dni[idx]
    except:
        return ""

# --- 3. INTERFEJS ---
st.set_page_config(page_title="AI Kalkulator Zarobków 2026", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    rok = st.selectbox("Rok:", [2025, 2026], index=1)
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka (zł/h):", value=25.0)
    # Zmiana domyślnej wartości na 15
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("🚀 Inteligentny Kalkulator Zarobków")

# Pobieranie danych o miesiącu
norma_godzin, lista_swiat = get_working_info(rok, m_idx)

tab1, tab2 = st.tabs(["🧮 Skanowanie i Wynik", "📊 Historia"])

with tab1:
    # Sekcja informacyjna o miesiącu
    with st.expander(f"📅 Szczegóły dla {m_nazwa} {rok}", expanded=False):
        st.write(f"Norma czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            st.write("Święta wolne od pracy:")
            for s in lista_swiat:
                st.write(f"• {s}")
        else:
            st.write("Brak świąt wypadających w dni robocze w tym miesiącu.")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=300)
        
        if st.button("🔍 Odczytaj grafik przez AI"):
            with st.spinner("Gemini analizuje pismo odręczne..."):
                try:
                    prompt = """Znajdź kolumnę 'Ilość godzin'. Odczytaj liczby dla dni 1-31. 
                    Zwróć dane TYLKO jako listę liczb oddzielonych przecinkami. Dla dni wolnych wpisz 0."""
                    response = model.generate_content([prompt, img])
                    numbers = re.findall(r"(\d+(?:\.\d+)?)", response.text)
                    parsed = [float(x) for x in numbers]
                    while len(parsed) < 31: parsed.append(0.0)
                    st.session_state['dni_lista'] = parsed[:31]
                    st.success("✅ Grafik odczytany pomyślnie!")
                except Exception as e:
                    st.error(f"Błąd analizy: {e}")

    # Sekcja korekty z nazwami dni tygodnia
    if 'dni_lista' in st.session_state:
        st.subheader("📝 Zweryfikuj odczytane godziny")
        poprawione = []
        cols = st.columns(7)
        num_days_in_month = calendar.monthrange(rok, m_idx)[1]

        for i in range(num_days_in_month):
            day_name = get_day_name(rok, m_idx, i + 1)
            with cols[i % 7]:
                val = st.number_input(f"Dz {i+1} {day_name}", value=st.session_state['dni_lista'][i], key=f"d_{i}", step=0.5)
                poprawione.append(val)
        
        # --- NOWA LOGIKA ROZLICZENIA ---
        suma_wszystkich = sum(poprawione)
        
        # Podział na standard i nadgodziny zgodnie z Twoją prośbą
        godziny_standard = min(suma_wszystkich, norma_godzin)
        godziny_nadliczbowe = max(0.0, suma_wszystkich - norma_godzin)
        
        # Oddzielnie liczymy soboty i niedziele/święta tylko dla informacji (płace)
        pl_hols = holidays.Poland(years=rok)
        h_sob = 0.0
        h_nie = 0.0
        for i, h in enumerate(poprawione):
            curr_d = date(rok, m_idx, i + 1)
            if curr_d.weekday() == 5: h_sob += h
            elif curr_d.weekday() == 6 or curr_d in pl_hols: h_nie += h

        # WYPŁATA: Standardowe godziny (wszystkie do poziomu normy) + bonus za nadwyżkę
        total_pln = (suma_wszystkich * stawka) + (godziny_nadliczbowe * dodatek)
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Suma wszystkich godzin", f"{suma_wszystkich} h")
        c2.metric("Norma miesięczna", f"{norma_godzin} h")
        c3.metric("Nadgodziny (Nadwyżka)", f"{godziny_nadliczbowe} h", delta=f"+{godziny_nadliczbowe}" if godziny_nadliczbowe > 0 else None)
        
        st.subheader(f"💰 Przewidywana wypłata: {total_pln:,.2f} zł brutto")
        
        with st.expander("Szczegóły rozliczenia"):
            st.write(f"• Podstawa: {suma_wszystkich} h × {stawka} zł = **{suma_wszystkich * stawka:,.2f} zł**")
            st.write(f"• Premia za nadgodziny: {godziny_nadliczbowe} h × {dodatek} zł = **{godziny_nadliczbowe * dodatek:,.2f} zł**")
            st.caption("Uwaga: Soboty i Niedziele są już wliczone w sumę godzin. Nadgodziny to każda minuta powyżej normy miesięcznej.")

with tab2:
    st.info("Sekcja historii (w przygotowaniu lub wklej kod z poprzednich wersji).")
