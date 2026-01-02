import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
import os
import calendar
from datetime import date, datetime
from PIL import Image, ImageOps

# --- 1. KONFIGURACJA AI (AUTOMATYCZNE WYKRYWANIE MODELU) ---
@st.cache_resource
def get_best_model():
    """Pobiera listę modeli z API i wybiera pierwszy działający Flash."""
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Listujemy wszystkie modele dostępne dla Twojego klucza
        models = genai.list_models()
        available_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        
        # Szukamy modelu Flash 1.5 w różnych wersjach
        for m_name in available_models:
            if "1.5-flash" in m_name:
                return genai.GenerativeModel(m_name), m_name
        
        # Jeśli nie ma 1.5, bierzemy jakikolwiek Flash
        for m_name in available_models:
            if "flash" in m_name:
                return genai.GenerativeModel(m_name), m_name
        
        return None, None
    except Exception as e:
        st.error(f"Problem z połączeniem z Google API: {e}")
        return None, None

model, active_model_name = get_best_model()

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

# --- 3. BAZA DANYCH EXCEL ---
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

# --- 4. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.header("⚙️ Ustawienia")
    cur_yr = datetime.now().year
    lata = list(range(2024, cur_yr + 11))
    rok = st.selectbox("Rok:", lata, index=lata.index(cur_yr))
    
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
              "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    m_idx = m_list.index(m_nazwa) + 1
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")

if active_model_name:
    st.caption(f"Status: Połączono z silnikiem `{active_model_name}`")

norma_godzin, lista_swiat = get_working_info(rok, m_idx)
tab1, tab2 = st.tabs(["🧮 Rozliczenie", "📊 Archiwum"])

with tab1:
    with st.expander(f"📅 Norma i informacje: {m_nazwa} {rok}"):
        st.write(f"Wymiar czasu pracy: **{norma_godzin} h**")
        if lista_swiat:
            for s in lista_swiat: st.write(f"• {s}")

    plik = st.file_uploader("Zrób zdjęcie lub wgraj grafik:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        # Korekta zdjęcia (ważne dla telefonów)
        img = Image.open(plik)
        img = ImageOps.exif_transpose(img)
        st.image(img, width=300, caption="Podgląd grafiku")
        
        if st.button("🚀 ANALIZUJ GRAFIK"):
            if not model:
                st.error("Błąd: Nie znaleziono aktywnego modelu AI dla Twojego klucza.")
            else:
                with st.spinner("AI analizuje pismo odręczne i urlopy..."):
                    try:
                        prompt = """To jest grafik pracy. Zlokalizuj kolumnę 'Ilość godzin'. 
                        Wypisz 31 wartości oddzielonych przecinkami dla dni 1-31.
                        ZASADY:
                        - Jeśli jest liczba (np. 8, 12), wpisz ją.
                        - Jeśli widzisz 'URL', 'Urlop', 'URZ', wpisz 'U'.
                        - Jeśli puste lub kreska, wpisz '0'."""
                        
                        response = model.generate_content([prompt, img])
                        items = response.text.replace(" ", "").split(",")
                        
                        p_hours, p_url = [], []
                        for i, item in enumerate(items[:31]):
                            if 'U' in item.upper():
                                p_hours.append(8.0)
                                p_url.append(i + 1)
                            else:
                                n = re.findall(r"(\d+(?:\.\d+)?)", item)
                                p_hours.append(float(n[0]) if n else 0.0)
                        
                        while len(p_hours) < 31: p_hours.append(0.0)
                        st.session_state['dni_lista'] = p_hours
                        st.session_state['url_dni'] = p_url
                        st.success("✅ Odczytano!")
                    except Exception as e: st.error(f"Błąd analizy: {e}")

    if 'dni_lista' in st.session_state:
        num_d = calendar.monthrange(rok, m_idx)[1]
        
        st.subheader("📝 Korekta i wyniki")
        
        sel_url = st.multiselect(
            "Dni oznaczone jako URLOP (8h):",
            options=range(1, num_d + 1),
            default=st.session_state.get('url_dni', []),
            format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})"
        )

        popr = []
        cols = st.columns(7)
        for i in range(num_d):
            d_n = i + 1
            with cols[i % 7]:
                d_val = 8.0 if d_n in sel_url else st.session_state['dni_lista'][i]
                v = st.number_input(f"{d_n} {get_day_name(rok, m_idx, d_n)}", 
                                    value=float(d_val), key=f"f_{i}", step=0.5)
                popr.append(v)
        
        suma_h = sum(popr)
        nadgodziny = max(0.0, suma_h - norma_godzin)
        total_pln = (suma_h * stawka) + (nadgodziny * dodatek)
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suma godzin", f"{suma_h} h")
        c2.metric("Norma etatu", f"{norma_godzin} h")
        c3.metric("Nadgodziny", f"{nadgodziny} h", delta=nadgodziny if nadgodziny > 0 else None)
        c4.metric("Dni urlopu", f"{len(sel_url)}")
        
        st.success(f"### 💰 Wypłata: **{total_pln:,.2f} zł brutto**")

        if st.button("💾 Zapisz do historii"):
            res = save_to_excel({
                "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
                "Norma": norma_godzin, "Nadgodziny": nadgodziny,
                "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total_pln, 2)
            })
            st.balloons()
            st.success("Zapisano pomyślnie!")

with tab2:
    df_db = load_data()
    if not df_db.empty:
        df_rok = df_db[df_db['Rok'] == rok].copy()
        if not df_rok.empty:
            df_rok['M_Idx'] = df_rok['Miesiąc'].apply(lambda x: m_list.index(x))
            df_rok = df_rok.sort_values('M_Idx')
            
            st.subheader(f"Zarobki w roku {rok}")
            st.bar_chart(df_rok, x="Miesiąc", y="Suma PLN")
            st.metric("Suma roczna", f"{df_rok['Suma PLN'].sum():,.2f} zł")
            st.metric("Wykorzystany urlop", f"{df_rok['Dni Urlopu'].sum()} dni")
            st.dataframe(df_rok[["Miesiąc", "Godziny Suma", "Nadgodziny", "Dni Urlopu", "Suma PLN"]], use_container_width=True)
            
            with open(DB_FILE, "rb") as f:
                st.download_button("📥 Pobierz bazę Excel", data=f, file_name=f"zarobki_{rok}.xlsx")
    else:
        st.info("Brak wpisów w historii.")
