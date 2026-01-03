import streamlit as st
import google.generativeai as genai
import pandas as pd
import holidays
import re
import calendar
from datetime import date, datetime
from PIL import Image, ImageOps
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.chart import BarChart, Reference
from io import BytesIO

# --- 1. KONFIGURACJA AI (WYMUSZENIE STABILNYCH MODELI) ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Unikamy wersji "exp" (eksperymentalnych), wybieramy stabilne Flash
        target_models = [
            "models/gemini-1.5-flash-8b", 
            "models/gemini-1.5-flash"
        ]
        
        for target in target_models:
            if target in available:
                return genai.GenerativeModel(target), target
        
        # Jeśli powyższe nie zadziałają, bierzemy pierwszy dostępny stabilny model
        stable_models = [m for m in available if "flash" in m and "exp" not in m]
        if stable_models:
            return genai.GenerativeModel(stable_models[0]), stable_models[0]
            
        return None, "Brak stabilnego modelu"
    except Exception as e:
        return None, f"Błąd: {str(e)}"

model, active_model_name = get_working_model()

# --- 2. FUNKCJE POMOCNICZE ---
M_LIST = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

def get_working_info(year, month):
    pl_hols = holidays.Poland(years=year)
    num_days = calendar.monthrange(year, month)[1]
    working_days = 0
    holiday_list = []
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date in pl_hols and curr_date.weekday() < 5:
            holiday_list.append(f"{day} {M_LIST[month-1]} - {pl_hols.get(curr_date)}")
        if curr_date.weekday() < 5 and curr_date not in pl_hols:
            working_days += 1
    return working_days * 8, holiday_list

def get_day_name(year, month, day):
    dni = ["Pon", "Wto", "Śro", "Czw", "Pią", "Sob", "Nie"]
    try: return dni[date(year, month, day).weekday()]
    except: return ""

def create_excel_with_stats(df_final, pil_image=None):
    # Sortowanie danych chronologicznie
    df_final['M_Idx'] = df_final['Miesiąc'].apply(lambda x: M_LIST.index(x))
    df_final = df_final.sort_values(['Rok', 'M_Idx']).drop(columns=['M_Idx'])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Zarobki')
        stats_df = df_final[['Miesiąc', 'Godziny Suma', 'Nadgodziny', 'Suma PLN']]
        stats_df.to_excel(writer, index=False, sheet_name='Statystyki')

    output.seek(0)
    wb = openpyxl.load_workbook(output)
    
    # Arkusz 1: Zarobki + Miniaturka zdjęcia
    ws1 = wb['Zarobki']
    if pil_image:
        row_idx = ws1.max_row
        img_temp = pil_image.copy()
        img_temp.thumbnail((1600, 2000))
        img_buf = BytesIO()
        img_temp.save(img_buf, format="PNG")
        img_xl = OpenpyxlImage(img_buf)
        img_xl.width, img_xl.height = 80, 105
        ws1.add_image(img_xl, f'I{row_idx}')
        ws1.row_dimensions[row_idx].height = 80
        ws1.column_dimensions['I'].width = 15

    # Arkusz 2: Statystyki + Wykresy (NAPRAWIONE NAWIASY)
    ws2 = wb['Statystyki']
    max_r = ws2.max_row
    if max_r > 1:
        # Wykresy: Godziny (B), Nadgodziny (C), PLN (D)
        for i, title in enumerate(["Suma Godzin", "Nadgodziny", "Zarobki PLN"], 2):
            chart = BarChart()
            chart.title = title
            data = Reference(ws2, min_col=i, min_row=1, max_row=max_r)
            cats = Reference(ws2, min_col=1, min_row=2, max_row=max_r)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            # Rozmieszczenie wykresów co 15 wierszy
            ws2.add_chart(chart, f"F{2 + (i-2)*15}")

    final_out = BytesIO()
    wb.save(final_out)
    return final_out.getvalue()

# --- 3. INTERFEJS UŻYTKOWNIKA ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.title("📂 Zarządzanie")
    uploaded_file = st.file_uploader("Wgraj swoją bazę (.xlsx):", type="xlsx")
    st.divider()
    st.header("⚙️ Ustawienia")
    cur_yr = datetime.now().year
    rok = st.selectbox("Rok:", list(range(2024, cur_yr + 11)), index=list(range(2024, cur_yr + 11)).index(cur_yr))
    m_nazwa = st.selectbox("Miesiąc:", M_LIST, index=datetime.now().month-1)
    stawka = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")
if active_model_name:
    st.caption(f"✅ Aktywny stabilny silnik: `{active_model_name}`")

# Obliczanie normy
m_idx = M_LIST.index(m_nazwa) + 1
norma_h, swieta = get_working_info(rok, m_idx)

with st.expander(f"📅 Norma i święta dla {m_nazwa} {rok}"):
    st.write(f"Wymiar czasu pracy: **{norma_h} h**")
    for s in swieta: st.write(f"• {s}")

plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])

if plik:
    img = ImageOps.exif_transpose(Image.open(plik))
    st.image(img, width=300)
    
    if st.button("🚀 SKANUJ GRAFIK"):
        if model:
            with st.spinner("Sztuczna inteligencja analizuje dane..."):
                try:
                    prompt = "Odczytaj kolumnę 'Ilość godzin' dla dni 1-31. Format: 1: [wart], 2: [wart]... Użyj 'U' dla urlopów."
                    response = model.generate_content([prompt, img])
                    
                    pairs = re.findall(r"(\d+):\s*([0-9.Uu]+)", response.text)
                    d_list = [0.0]*31
                    u_list = []
                    for d, v in pairs:
                        dn = int(d)
                        if dn <= 31:
                            if v.upper() == 'U':
                                d_list[dn-1] = 8.0
                                u_list.append(dn)
                            else:
                                try: d_list[dn-1] = float(v)
                                except: pass
                    st.session_state['dni_lista'] = d_list
                    st.session_state['url_dni'] = u_list
                    st.session_state['last_img'] = img
                    st.success("✅ Odczytano!")
                except Exception as e:
                    if "429" in str(e):
                        st.error("⚠️ Przekroczono limit zapytań AI. Odczekaj minutę lub spróbuj jutro.")
                    else:
                        st.error(f"Błąd AI: {e}")

# Sekcja Korekty
if 'dni_lista' in st.session_state:
    st.divider()
    num_days_in_month = calendar.monthrange(rok, m_idx)[1]
    st.subheader("📝 Korekta i wyniki")
    
    sel_url = st.multiselect("Dni urlopowe (8h):", range(1, num_days_in_month + 1), 
                             default=st.session_state.get('url_dni', []),
                             format_func=lambda x: f"Dzień {x} ({get_day_name(rok, m_idx, x)})")

    popr = []
    c_l, c_r = st.columns(2)
    for i in range(num_days_in_month):
        dn = i + 1
        with (c_l if i < num_days_in_month/2 else c_r):
            d_init = 8.0 if dn in sel_url else st.session_state['dni_lista'][i]
            v = st.number_input(f"Dz {dn} ({get_day_name(rok, m_idx, dn)})", 
                                value=float(d_init), step=0.5, key=f"inp_{i}")
            popr.append(v)
    
    suma_h = sum(popr)
    nadgodziny = max(0.0, suma_h - norma_h)
    total = (suma_h * stawka) + (nadgodziny * dodatek)
    
    st.info(f"### 💰 Wypłata: **{total:,.2f} zł brutto**")
    
    if st.button("📊 Generuj plik Excel ze statystykami"):
        new_row = {
            "Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h,
            "Norma": norma_h, "Nadgodziny": nadgodziny,
            "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total, 2)
        }
        df_base = pd.read_excel(uploaded_file) if uploaded_file else pd.DataFrame(columns=new_row.keys())
        mask = (df_base['Rok'] == rok) & (df_base['Miesiąc'] == m_nazwa)
        df_base = df_base[~mask]
        df_final = pd.concat([df_base, pd.DataFrame([new_row])], ignore_index=True)
        
        st.session_state['excel_ready'] = create_excel_with_stats(df_final, st.session_state.get('last_img'))
        st.success("✅ Plik gotowy!")

    if 'excel_ready' in st.session_state:
        st.download_button(
            label="📥 POBIERZ AKTUALNY PLIK EXCEL",
            data=st.session_state['excel_ready'],
            file_name=f"zarobki_{rok}_{m_nazwa}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
