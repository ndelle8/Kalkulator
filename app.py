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
    cols = ["Rok", "Miesiąc", "Godziny Suma", "Norma", "Nadgodziny", "Stawka", "Dni Urlopu", "Suma PLN"]
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_excel(DB_FILE)
            for col in cols:
                if col not in df.columns: df[col] = 0
            return df
        except:
            return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def save_to_excel(new_data):
    df = load_data()
    mask = (df['Rok'] == new_data['Rok']) & (df['Miesiąc'] == new_data['Miesiąc'])
    if any(mask): df = df[~mask]
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_excel(DB_FILE, index=False)
    return df

# --- 4. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    current_year = datetime.now().year
    lata = list(range(2024, current_year + 11))
    rok = st.selectbox("Rok:", lata, index=lata.index(current_year) if current_year in lata else 0)
    
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)
tab1, tab2 = st.tabs(["🧮 Rozliczenie i Skanowanie", "📊 Archiwum i Statystyki"])

with tab1:
    with st.expander(f"📅 Norma i informacje: {m_nazwa} {rok}", expanded=False):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            for s in lista_swiat: st.write(f"• {s}")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=300)
        if st.button("🔍 Skanuj grafik przez AI"):
            if model:
                with st.spinner("Gemini analizuje pismo odręczne..."):
                    try:
                        # TUTAJ BYŁ BŁĄD - TERAZ JEST POPRAWNIE DOMKNIĘTY CUDZYSŁÓW
                        prompt = """Odczytaj 4. kolumnę (Ilość godzin). Zwróć 31 wartości oddzielonych przecinkami. 
                        Jeśli widzisz liczbę, wpisz ją. Jeśli widzisz 'URL', 'Urlop' lub 'URZ', wpisz literę 'U'. 
                        Reszta (kreski, puste) to 0."""
                        
                        response = model.generate_content([prompt, img])
                        items = response.text.replace(" ", "").split(",")
                        
                        parsed_hours = []
                        urlopy_indices = []
                        
                        for i, item in enumerate(items[:31]):
                            if 'U' in item.upper():
                                parsed_hours.append(8.0)
                                urlopy_indices.append(i + 1)
                            else:
                                val = re.findall(r"(\d+(?:\.\d+)?)", item)
                                parsed_hours.append(float(val[0]) if val else 0.0)
                        
                        while len(parsed_hours) < 31: parsed_hours.append(0.0)
                        
                        st.session_state['dni_lista'] = parsed_hours[:31]
                        st.session_state['urlopy_dni'] = [d for d in urlopy_indices if d <= 31]
                        st.success("✅ Grafik odczytany pomyślnie!")
                    except Exception as e: st.error(f"Błąd analizy AI: {e}")

    if 'dni_lista' in st.session_state:
        st.subheader("📝 Korekta godzin i urlopów")
        num_days_in_month = calendar.monthrange(rok, m_idx)[1]
        
        wybrane_urlopy = st.multiselect(
            "Zaznacz dni urlopowe (8h):",
            options=range(1, num_days_in_month + 1),
            default=st.session_state.get('urlopy_dni', []),
            format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})"
        )

        poprawione = []
        cols = st.columns(7)
        for i in range(num_days_in_month):
            day_num = i + 1
            with cols[i % 7]:
                default_val = 8.0 if day_num in wybrane_urlopy else st.session_state['dni_lista'][i]
                val = st.number_input(f"{day_num} {get_day_name(rok, m_idx, day_num)}", value=float(default_val), key=f"d_{i}", step=0.5)
                poprawione.append(val)
        
        suma_wszystkich = sum(poprawione)
        nadgodziny_bilans = max(0.0, suma_wszystkich - norma_godzin)
        total_pln = (suma_wszystkich * stawka) + (nadgodziny_bilans * dodatek)
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suma godzin", f"{suma_wszystkich} h")
        c2.metric("Norma etatu", f"{norma_godzin} h")
        c3.metric("Nadgodziny", f"{nadgodziny_bilans} h")
        c4.metric("Dni urlopu", f"{len(wybrane_urlopy)}")
        
        st.success(f"### Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("Zapisz do historii"):
            new_entry = {
                "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_wszystkich,
                "Norma": norma_godzin, "Nadgodziny": nadgodziny_bilans,
                "Stawka": stawka, "Dni Urlopu": len(wybrane_urlopy), "Suma PLN": round(total_pln, 2)
            }
            save_to_excel(new_entry)
            st.balloons()
            st.success(f"Dane za {m_nazwa} zapisane!")

with tab2:
    st.subheader(f"📊 Statystyki: {rok}")
    df_db = load_data()
    if not df_db.empty:
        df_rok = df_db[df_db['Rok'] == rok].copy()
        if not df_rok.empty:
            df_rok['M_Idx'] = df_rok['Miesiąc'].apply(lambda x: m_list.index(x))
            df_rok = df_rok.sort_values('M_Idx')
            
            c_s1, c_s2 = st.columns(2)
            c_s1.metric("Zarobki roczne", f"{df_rok['Suma PLN'].sum():,.2f} zł")
            c_s2.metric("Suma urlopów", f"{df_rok['Dni Urlopu'].sum()} dni")

            st.bar_chart(df_rok, x="Miesiąc", y="Suma PLN")
            st.dataframe(df_rok[["Miesiąc", "Godziny Suma", "Nadgodziny", "Dni Urlopu", "Suma PLN"]], use_container_width=True)
            
            with open(DB_FILE, "rb") as f:
                st.download_button("📥 Pobierz Excel", data=f, file_name=f"zarobki_{rok}.xlsx")
    else:
        st.info("Brak danych w historii.")
