import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
from datetime import date, datetime
import calendar

# --- 1. KONFIGURACJA AI ---
# Klucz pobierany z Secrets
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

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
        except: continue
    return stats

# --- 3. INTERFEJS ---
st.set_page_config(page_title="AI Kalkulator Zarobków", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    rok = st.selectbox("Rok:", [2025, 2026], index=1)
    m_nazwa = st.selectbox("Miesiąc:", ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"], index=datetime.now().month-1)
    m_idx = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"].index(m_nazwa) + 1
    stawka = st.number_input("Stawka (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=30.0)

st.title("🚀 Inteligentny Kalkulator (Powered by Gemini)")

tab1, tab2 = st.tabs(["🧮 Obliczenia i Skanowanie", "📊 Historia"])

with tab1:
    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        st.image(plik, width=400)
        if st.button("🔍 Odczytaj grafik przez AI"):
            with st.spinner("Gemini analizuje pismo odręczne..."):
                # Wysyłamy zdjęcie do Gemini z instrukcją
                img_data = plik.getvalue()
                prompt = "To jest grafik pracy. Odczytaj liczby z 4. kolumny (Ilość godzin) dla dni od 1 do 31. Zwróć mi TYLKO listę 31 liczb oddzielonych przecinkami. Jeśli dzień jest pusty lub ma kreskę, wpisz 0."
                
                response = model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': img_data}])
                
                # Przetwarzanie odpowiedzi na listę liczb
                try:
                    raw_list = response.text.strip().split(',')
                    st.session_state['dni_lista'] = [float(re.sub(r'[^\d.]', '', x)) for x in raw_list]
                    st.success("✅ Odczytano pismo odręczne!")
                except:
                    st.error("AI zwróciło dane w złym formacie. Spróbuj ponownie.")

    # Sekcja korekty i wynik
    if 'dni_lista' in st.session_state:
        st.subheader("📝 Sprawdź odczytane dane")
        poprawione = []
        cols = st.columns(7)
        for i in range(31):
            with cols[i % 7]:
                val = st.number_input(f"Dz {i+1}", value=st.session_state['dni_lista'][i], key=f"d_{i}")
                poprawione.append(val)
        
        res = calculate_wages(poprawione, rok, m_idx, stawka, dodatek)
        
        # Obliczenie sumy
        # $$Suma = (h_{std} \cdot stawka) + (h_{nad} \cdot (stawka + dodatek)) + (h_{sob} \cdot stawka \cdot 1.5) + (h_{nie} \cdot stawka \cdot 2.0)$$
        total = (res["std"] * stawka) + (res["nad"] * (stawka + dodatek)) + (res["sob"] * stawka * 1.5) + (res["nie"] * stawka * 2.0)
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Standard", f"{res['std']}h")
        c2.metric("Nadgodziny", f"{res['nad']}h")
        c3.metric("Soboty", f"{res['sob']}h")
        c4.metric("Nd/Święta", f"{res['nie']}h")
        st.metric("WYPŁATA BRUTTO", f"{total:,.2f} zł")
