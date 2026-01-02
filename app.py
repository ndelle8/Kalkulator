import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
from datetime import date, datetime
import calendar
from PIL import Image

# --- 1. KONFIGURACJA AI ---
# Klucz musi być w Secrets jako: GOOGLE_API_KEY = "..."
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # Zmieniono na 'gemini-1.5-flash-latest' - najbardziej odporna na błędy 404 nazwa
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    st.error(f"Problem z konfiguracją Google AI: {e}")

# --- 2. LOGIKA OBLICZEŃ ---
def calculate_wages(hours_list, year, month, rate, bonus):
    stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
    pl_hols = holidays.Poland(years=year)
    
    for i, h in enumerate(hours_list):
        if h <= 0: continue
        try:
            # i to indeks (0-30), więc i+1 to dzień miesiąca
            curr_d = date(year, month, i + 1)
            wday = curr_d.weekday()
            # 5 = Sobota, 6 = Niedziela
            if wday == 5: stats["sob"] += h
            elif wday == 6 or curr_d in pl_hols: stats["nie"] += h
            else:
                if h > 8:
                    stats["std"] += 8
                    stats["nad"] += (h - 8)
                else: stats["std"] += h
        except ValueError:
            # Obsługa miesięcy krótszych niż 31 dni
            continue
    return stats

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
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=30.0)

st.title("🚀 Inteligentny Kalkulator (Gemini AI)")

tab1, tab2 = st.tabs(["🧮 Skanowanie i Wynik", "📊 Historia"])

with tab1:
    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=400)
        
        if st.button("🔍 Odczytaj grafik przez AI"):
            with st.spinner("Gemini analizuje pismo odręczne..."):
                try:
                    # Prompt z instrukcją "Zero-Shot"
                    prompt = """Znajdź kolumnę 'Ilość godzin' na zdjęciu. 
                    Odczytaj wartości dla dni 1-31. 
                    Zwróć dane TYLKO jako listę liczb oddzielonych przecinkami.
                    Dla dni wolnych lub pustych wpisz 0.
                    Przykład: 8,8,0,0,12,8..."""
                    
                    response = model.generate_content([prompt, img])
                    
                    # Oczyszczanie tekstu z ewentualnych komentarzy AI
                    raw_text = response.text
                    # Wyciągamy tylko to, co wygląda na liczby (całkowite lub z kropką)
                    numbers = re.findall(r"(\d+(?:\.\d+)?)", raw_text)
                    
                    parsed_numbers = [float(x) for x in numbers]
                    
                    # Zapewnienie, że mamy dokładnie 31 dni (dopełnienie zerami)
                    while len(parsed_numbers) < 31:
                        parsed_numbers.append(0.0)
                        
                    st.session_state['dni_lista'] = parsed_numbers[:31]
                    st.success("✅ Grafik odczytany pomyślnie!")
                except Exception as e:
                    st.error(f"Błąd analizy: {e}")
                    st.info("Jeśli widzisz błąd 404, sprawdź czy klucz API jest poprawny w Secrets.")

    # Sekcja korekty i wyniki
    if 'dni_lista' in st.session_state:
        st.subheader("📝 Sprawdź i popraw odczytane godziny")
        poprawione = []
        # Wyświetlamy 7 kolumn (jak w kalendarzu)
        cols = st.columns(7)
        for i in range(31):
            with cols[i % 7]:
                val = st.number_input(f"Dz {i+1}", value=st.session_state['dni_lista'][i], key=f"d_{i}", step=0.5)
                poprawione.append(val)
        
        # Wyliczenia
        res = calculate_wages(poprawione, rok, m_idx, stawka, dodatek)
        total = (res["std"] * stawka) + (res["nad"] * (stawka + dodatek)) + \
                (res["sob"] * stawka * 1.5) + (res["nie"] * stawka * 2.0)
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Standard", f"{res['std']}h")
        c2.metric("Nadgodziny", f"{res['nad']}h")
        c3.metric("Soboty", f"{res['sob']}h")
        c4.metric("Nd/Święta", f"{res['nie']}h")
        
        st.metric("WYPŁATA BRUTTO", f"{total:,.2f} zł")
