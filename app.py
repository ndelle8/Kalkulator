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
            if p in available: return genai.GenerativeModel(p), p
        fallback = [m for m in available if "flash" in m]
        if fallback: return genai.GenerativeModel(fallback[0]), fallback[0]
        return None, None
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None, None

model, active_model_name = get_working_model()

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
        except: return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def save_to_excel(new_data):
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
    current_year = datetime.now().year
    lata = list(range(2024, current_year + 11))
    rok = st.selectbox("Rok:", lata, index=lata.index(current_year))
    
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
    with st.expander(f"📅 Norma dla {m_nazwa} {rok}"):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            for s in lista_swiat: st.write(f"• {s}")

    plik = st.file_uploader("Zrób zdjęcie lub wgraj grafik:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        raw_img = Image.open(plik)
        img = ImageOps.exif_transpose(raw_img) # Korekta orientacji dla telefonów
        st.image(img, width=300)
        
        if st.button("🚀 ANALIZUJ GRAFIK"):
            with st.spinner("AI analizuje grafik..."):
                try:
                    prompt = f"""To jest grafik na {m_nazwa} {rok}. Odczytaj 4. kolumnę (Ilość godzin). 
                    Zwróć dane DOKŁADNIE w formacie: 1:[wartość], 2:[wartość], ..., 31:[wartość].
                    ZASADY:
                    - Liczba (np. 8, 10.5) -> wpisz ją.
                    - 'URL', 'Urlop', 'URZ' -> wpisz 'U'.
                    - Puste/Kreska -> wpisz '0'."""
                    
                    response = model.generate_content([prompt, img])
                    text_res = response.text
                    
                    day_map = {}
                    pairs = re.findall(r"(\d+):\s*([0-9.Uu]+)", text_res)
                    for day, val in pairs:
                        d_num = int(day)
                        if val.upper() == 'U': day_map[d_num] = ('U', 8.0)
                        else:
                            try: day_map[d_num] = ('H', float(val))
                            except: day_map[d_num] = ('H', 0.0)
                    
                    final_h, final_u = [], []
                    for d in range(1, 32):
                        v_type, v_val = day_map.get(d, ('H', 0.0))
                        final_h.append(v_val)
                        if v_type == 'U': final_u.append(d)
                        
                    st.session_state['dni_lista'] = final_h
                    st.session_state['url_dni'] = final_u
                    st.success("✅ Odczytano!")
                except Exception as e: st.error(f"Błąd analizy: {e}")

    if 'dni_lista' in st.session_state:
        num_d = calendar.monthrange(rok, m_idx)[1]
        st.subheader("📝 Korekta i wyniki")
        
        sel_url = st.multiselect(
            "Zaznacz dni URLOPU (liczone jako 8h):",
            options=range(1, num_d + 1),
            default=st.session_state.get('url_dni', []),
            format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})"
        )

        popr = []
        # FIX KOLEJNOŚCI: Wyświetlamy dni jeden po drugim
        # Na komputerze będą w dwóch szerokich kolumnach, na telefonie jeden pod drugim chronologicznie
        c_left, c_right = st.columns(2)
        for i in range(num_d):
            d_n = i + 1
            d_name = get_day_name(rok, m_idx, d_n)
            with (c_left if i < num_d/2 else c_right):
                d_init = 8.0 if d_n in sel_url else st.session_state['dni_lista'][i]
                v = st.number_input(f"Dzień {d_n} ({d_name})", value=float(d_init), key=f"k_{i}", step=0.5)
                popr.append(v)
        
        # OBLICZENIA BILANSOWE
        suma_h = sum(popr)
        nadgodziny = max(0.0, suma_h - norma_godzin)
        total_pln = (suma_h * stawka) + (nadgodziny * dodatek)
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suma godzin", f"{suma_h} h")
        c2.metric("Norma etatu", f"{norma_godzin} h")
        c3.metric("Nadgodziny", f"{nadgodziny} h")
        c4.metric("Dni urlopu", len(sel_url))
        
        st.success(f"### 💰 Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("💾 Zapisz do historii Excel"):
            save_to_excel({
                "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
                "Norma": norma_godzin, "Nadgodziny": nadgodziny,
                "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total_pln, 2)
            })
            st.balloons()
            st.success("Zapisano pomyślnie!")

with tab2:
    st.subheader(f"📊 Statystyki Roczne: {rok}")
    df_db = load_data()
    if not df_db.empty:
        df_rok = df_db[df_db['Rok'] == rok].copy()
        if not df_rok.empty:
            df_rok['M_Idx'] = df_rok['Miesiąc'].apply(lambda x: m_list.index(x))
            df_rok = df_rok.sort_values('M_Idx')
            
            st.bar_chart(df_rok, x="Miesiąc", y="Suma PLN")
            st.metric("Suma roczna", f"{df_rok['Suma PLN'].sum():,.2f} zł")
            st.metric("Suma urlopów", f"{df_rok['Dni Urlopu'].sum()} dni")
            st.dataframe(df_rok[["Miesiąc", "Godziny Suma", "Nadgodziny", "Dni Urlopu", "Suma PLN"]], use_container_width=True)
            
            with open(DB_FILE, "rb") as f:
                st.download_button("📥 Pobierz bazę Excel", data=f, file_name=f"zarobki_{rok}.xlsx")
    else:
        st.info("Baza danych jest pusta.")
