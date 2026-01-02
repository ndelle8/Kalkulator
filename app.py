import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
from datetime import date, datetime
import calendar
from PIL import Image

# --- 1. KONFIGURACJA AI I AUTO-DETEKCJA ---
st.set_page_config(page_title="AI Kalkulator Zarobków 2026", layout="wide")

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    
    # Funkcja do znalezienia działającego modelu Flash
    @st.cache_resource
    def get_flash_model_name():
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Szukamy najpierw 1.5-flash, potem jakiegokolwiek flash
        flash_models = [m for m in available_models if "1.5-flash" in m]
        if not flash_models:
            flash_models = [m for m in available_models if "flash" in m]
        
        return flash_models[0] if flash_models else "models/gemini-1.5-flash"

    model_name = get_flash_model_name()
    model = genai.GenerativeModel(model_name)
except Exception as e:
    st.error(f"Problem z dostępem do Google AI: {e}")
    model = None

# --- 2. LOGIKA OBLICZEŃ ---
def calculate_wages(hours_list, year, month, rate, bonus):
    stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
    pl_hols = holidays.Poland(years=year)
    
    for i, h in enumerate(hours_list):
        if h <= 0: continue
        try:
            curr_d = date(year, month, i + 1)
            wday = curr_d.weekday()
            if wday == 5: stats["sob"] += h
            elif wday == 6 or curr_d in pl_hols: stats["nie"] += h
            else:
                if h > 8:
                    stats["std"] += 8
                    stats["nad"] += (h - 8)
                else: stats["std"] += h
        except ValueError: continue
    return stats

# --- 3. INTERFEJS ---
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
    if model:
        st.caption(f"Połączono z modelem: `{model_name}`")
    
    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        st.image(img, width=400)
        
        if st.button("🔍 Odczytaj grafik przez AI"):
            if not model:
                st.error("Model AI nie jest gotowy. Sprawdź klucz API.")
            else:
                with st.spinner("Gemini analizuje pismo odręczne..."):
                    try:
                        prompt = """Odczytaj z tego grafiku 4. kolumnę (Ilość godzin). 
                        Zwróć TYLKO listę 31 liczb oddzielonych przecinkami dla dni 1-31. 
                        Wpisz 0 dla dni wolnych. Przykład: 8,8,0,10,8,0..."""
                        
                        response = model.generate_content([prompt, img])
                        numbers = re.findall(r"(\d+(?:\.\d+)?)", response.text)
                        
                        parsed = [float(x) for x in numbers]
                        while len(parsed) < 31: parsed.append(0.0)
                        
                        st.session_state['dni_lista'] = parsed[:31]
                        st.success("✅ Odczytano pismo odręczne!")
                    except Exception as e:
                        st.error(f"Błąd analizy: {e}")

    # Sekcja korekty i wyniki
    if 'dni_lista' in st.session_state:
        st.subheader("📝 Sprawdź i popraw godziny")
        poprawione = []
        cols = st.columns(7)
        for i in range(31):
            with cols[i % 7]:
                val = st.number_input(f"Dz {i+1}", value=st.session_state['dni_lista'][i], key=f"d_{i}", step=0.5)
                poprawione.append(val)
        
        res = calculate_wages(poprawione, rok, m_idx, stawka, dodatek)
        
        # Wzór na wynagrodzenie brutto
        # $$Suma = (h_{std} \cdot stawka) + (h_{nad} \cdot (stawka + dodatek)) + (h_{sob} \cdot stawka \cdot 1.5) + (h_{nie} \cdot stawka \cdot 2.0)$$
        total = (res["std"] * stawka) + (res["nad"] * (stawka + dodatek)) + \
                (res["sob"] * stawka * 1.5) + (res["nie"] * stawka * 2.0)
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Standard", f"{res['std']}h")
        c2.metric("Nadgodziny", f"{res['nad']}h")
        c3.metric("Soboty", f"{res['sob']}h")
        c4.metric("Nd/Święta", f"{res['nie']}h")
        
        st.metric("WYPŁATA BRUTTO", f"{total:,.2f} zł")
