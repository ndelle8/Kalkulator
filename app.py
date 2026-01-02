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
    if os.path.exists(DB_FILE):
        return pd.read_excel(DB_FILE)
    return pd.DataFrame(columns=["Rok", "Miesiąc", "Godziny Suma", "Norma", "Nadgodziny", "Stawka", "Suma PLN"])

def save_to_excel(new_data):
    df = load_data()
    # Sprawdzenie czy wpis dla tego miesiąca i roku już istnieje
    mask = (df['Rok'] == new_data['Rok']) & (df['Miesiąc'] == new_data['Miesiąc'])
    if any(mask):
        df = df[~mask] # Usuwamy stary wpis, by go zastąpić nowym
    
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_excel(DB_FILE, index=False)
    return df

# --- 4. INTERFEJS ---
st.set_page_config(page_title="AI Kalkulator Zarobków", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    # DYNAMICZNA LISTA LAT: od 2024 do obecny rok + 5
    current_year = datetime.now().year
    lata = list(range(2024, current_year + 6))
    rok = st.selectbox("Rok:", lata, index=lata.index(current_year))
    
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("💰 Inteligentny Kalkulator i Archiwum Zarobków")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)
tab1, tab2 = st.tabs(["🧮 Rozliczenie i Skanowanie", "📊 Archiwum i Suma Roczna"])

with tab1:
    with st.expander(f"📅 Norma dla {m_nazwa} {rok}"):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            for s in lista_swiat: st.write(f"• {s}")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=300)
        if st.button("🔍 Skanuj przez Gemini AI"):
            if model:
                with st.spinner("AI analizuje grafik..."):
                    try:
                        prompt = "Odczytaj 4. kolumnę (Ilość godzin). Zwróć 31 liczb oddzielonych przecinkami. Dni wolne = 0."
                        response = model.generate_content([prompt, img])
                        numbers = re.findall(r"(\d+(?:\.\d+)?)", response.text)
                        parsed = [float(x) for x in numbers]
                        while len(parsed) < 31: parsed.append(0.0)
                        st.session_state['dni_lista'] = parsed[:31]
                        st.success("✅ Odczytano!")
                    except Exception as e: st.error(f"Błąd AI: {e}")

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
        
        suma_wszystkich = sum(poprawione)
        nadgodziny_bilans = max(0.0, suma_wszystkich - norma_godzin)
        total_pln = (suma_wszystkich * stawka) + (nadgodziny_bilans * dodatek)
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Suma godzin", f"{suma_wszystkich} h")
        c2.metric("Norma etatu", f"{norma_godzin} h")
        c3.metric("Nadgodziny", f"{nadgodziny_bilans} h")
        st.success(f"### 💰 Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("💾 Zapisz ten miesiąc do bazy danych Excel"):
            new_entry = {
                "Rok": rok,
                "Miesiąc": m_nazwa,
                "Godziny Suma": suma_wszystkich,
                "Norma": norma_godzin,
                "Nadgodziny": nadgodziny_bilans,
                "Stawka": stawka,
                "Suma PLN": round(total_pln, 2)
            }
            save_to_excel(new_entry)
            st.balloons()
            st.success(f"Miesiąc {m_nazwa} został pomyślnie dodany do arkusza!")

with tab2:
    st.subheader(f"📊 Zestawienie za rok {rok}")
    df_db = load_data()
    
    if not df_db.empty:
        # Filtrowanie danych dla wybranego roku
        df_rok = df_db[df_db['Rok'] == rok]
        
        if not df_rok.empty:
            suma_roczna = df_rok['Suma PLN'].sum()
            st.metric(f"📈 ŁĄCZNIE ZAROBIONE W {rok}", f"{suma_roczna:,.2f} zł")
            
            st.write("Szczegóły miesięcy:")
            st.dataframe(df_rok, use_container_width=True)
            
            # Przycisk pobierania pliku Excel
            with open(DB_FILE, "rb") as file:
                st.download_button(
                    label="📥 Pobierz całą bazę jako plik Excel",
                    data=file,
                    file_name="zarobki_baza.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info(f"Brak wpisów dla roku {rok} w bazie danych.")
        
        st.divider()
        st.write("Cała zawartość bazy (wszystkie lata):")
        st.dataframe(df_db, use_container_width=True)
    else:
        st.info("Baza danych jest pusta. Zapisz pierwsze rozliczenie w zakładce obok.")
