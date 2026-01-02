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
from io import BytesIO

# --- 1. KONFIGURACJA AI (PRIORYTET DLA MODELI O WYSOKICH LIMITACH) ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Priorytet dla Flash-8B (najwyższe limity)
        priorities = [
            "models/gemini-1.5-flash-8b", 
            "models/gemini-1.5-flash", 
            "models/gemini-1.5-flash-latest"
        ]
        
        for p in priorities:
            if p in available_models:
                return genai.GenerativeModel(p), p
        
        # Jeśli nic z listy, bierzemy pierwszy dostępny flash
        fallbacks = [m for m in available_models if "flash" in m]
        if fallbacks:
            return genai.GenerativeModel(fallbacks[0]), fallbacks[0]
            
        return None, None
    except Exception:
        return None, None

model, model_name = get_working_model()

# --- 2. FUNKCJE POMOCNICZE ---
def get_working_info(year, month):
    pl_hols = holidays.Poland(years=year)
    num_days = calendar.monthrange(year, month)[1]
    working_days = 0
    holiday_list = []
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

def create_excel_in_memory(df_final, pil_image=None):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Zarobki')
    
    if pil_image:
        output.seek(0)
        wb = openpyxl.load_workbook(output)
        ws = wb.active
        row_idx = ws.max_row
        
        img_temp = pil_image.copy()
        img_temp.thumbnail((1600, 2000)) # Wysoka jakość do powiększania
        img_buffer = BytesIO()
        img_temp.save(img_buffer, format="PNG")
        
        img_to_excel = OpenpyxlImage(img_buffer)
        img_to_excel.width, img_to_excel.height = 80, 105 # Mała miniaturka
        
        ws.add_image(img_to_excel, f'I{row_idx}')
        ws.row_dimensions[row_idx].height = 80
        ws.column_dimensions['I'].width = 12
        
        final_out = BytesIO()
        wb.save(final_out)
        return final_out.getvalue()
    return output.getvalue()

# --- 3. INTERFEJS ---
st.set_page_config(page_title="Kalkulator czasu pracy", layout="wide")

with st.sidebar:
    st.title("📂 Zarządzanie")
    uploaded_file = st.file_uploader("Wgraj bazę .xlsx:", type="xlsx")
    st.divider()
    st.header("⚙️ Ustawienia")
    cur_year = datetime.now().year
    rok = st.selectbox("Rok:", list(range(2024, cur_year + 11)), index=list(range(2024, cur_year + 11)).index(cur_year))
    m_list = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    m_nazwa = st.selectbox("Miesiąc:", m_list, index=datetime.now().month-1)
    stawka = st.number_input("Stawka (zł/h):", value=25.0)
    dodatek = st.number_input("Dodatek za nadgodziny (zł):", value=15.0)

st.title("Kalkulator czasu pracy")
if model_name:
    st.caption(f"Używany model: `{model_name}` (Wysoki limit zapytania)")

tab1, tab2 = st.tabs(["🧮 Rozliczenie", "📊 Historia i Eksport"])

with tab1:
    norma_h, swieta = get_working_info(rok, m_list.index(m_nazwa)+1)
    with st.expander(f"📅 Norma dla {m_nazwa} {rok}"):
        st.write(f"Wymiar czasu pracy: **{norma_h} h**")
        for s in swieta: st.write(f"• {s}")

    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = ImageOps.exif_transpose(Image.open(plik))
        st.image(img, width=300)
        
        if st.button("🚀 SKANUJ GRAFIK"):
            try:
                with st.spinner("AI analizuje grafik..."):
                    prompt = "Odczytaj 4. kolumnę (Ilość godzin). Zwróć dane: 1:[wart], 2:[wart]... Użyj 'U' dla urlopów."
                    response = model.generate_content([prompt, img])
                    pairs = re.findall(r"(\d+):\s*([0-9.Uu]+)", response.text)
                    
                    d_list, u_list = [0.0]*31, []
                    for d, v in pairs:
                        dn = int(d)
                        if dn <= 31:
                            if v.upper() == 'U': d_list[dn-1] = 8.0; u_list.append(dn)
                            else:
                                try: d_list[dn-1] = float(v)
                                except: pass
                    st.session_state['dni_lista'] = d_list
                    st.session_state['url_dni'] = u_list
                    st.session_state['last_img'] = img
                    st.success("✅ Odczytano!")
            except Exception as e:
                if "429" in str(e):
                    st.error("⚠️ Limit zapytań wyczerpany. Poczekaj minutę i spróbuj ponownie.")
                else:
                    st.error(f"Błąd: {e}")

    if 'dni_lista' in st.session_state:
        num_d = calendar.monthrange(rok, m_list.index(m_nazwa)+1)[1]
        sel_url = st.multiselect("Dni urlopowe:", range(1, num_d + 1), default=st.session_state.get('url_dni', []))
        
        popr = []
        c_l, c_r = st.columns(2)
        for i in range(num_d):
            dn = i + 1
            with (c_l if i < num_d/2 else c_r):
                d_init = 8.0 if dn in sel_url else st.session_state['dni_lista'][i]
                v = st.number_input(f"Dz {dn} ({get_day_name(rok, m_list.index(m_nazwa)+1, dn)})", value=float(d_init), step=0.5, key=f"k_{i}")
                popr.append(v)
        
        suma_h = sum(popr)
        nadgodziny = max(0.0, suma_h - norma_h)
        # Obliczenie wynagrodzenia:
        # $$Wynagrodzenie = (h_{suma} \cdot stawka) + (h_{nadgodziny} \cdot dodatek)$$
        total = (suma_h * stawka) + (nadgodziny * dodatek)
        
        st.divider()
        st.success(f"### 💰 Wypłata BRUTTO: **{total:,.2f} zł**")

        if st.button("➕ Przygotuj plik do pobrania"):
            new_row = {"Rok": rok, "Miesiąc": m_nazwa, "Godziny Suma": suma_h, "Norma": norma_h, "Nadgodziny": nadgodziny, "Stawka": stawka, "Dni Urlopu": len(sel_url), "Suma PLN": round(total, 2)}
            df_base = pd.read_excel(uploaded_file) if uploaded_file else pd.DataFrame(columns=new_row.keys())
            df_final = pd.concat([df_base[(df_base.Rok != rok) | (df_base.Miesiąc != m_nazwa)], pd.DataFrame([new_row])], ignore_index=True)
            st.session_state['excel_ready'] = create_excel_in_memory(df_final, st.session_state.get('last_img'))
            st.info("Zaktualizowany plik gotowy do pobrania w zakładce obok.")

with tab2:
    if 'excel_ready' in st.session_state:
        st.download_button("📥 POBIERZ AKTUALNY EXCEL", data=st.session_state['excel_ready'], file_name=f"kalkulator_zarobki_{rok}.xlsx")
    elif uploaded_file:
        st.dataframe(pd.read_excel(uploaded_file), use_container_width=True)
