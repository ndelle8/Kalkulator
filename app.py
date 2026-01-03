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

# --- 1. DYNAMICZNA KONFIGURACJA AI ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Pobieramy listę modeli dostępnych dla Twojego regionu i klucza
        available_models = genai.list_models()
        model_names = [m.name for m in available_models if 'generateContent' in m.supported_generation_methods]
        
        # Szukamy modelu Flash (najszybszy i najstabilniejszy dla darmowych kluczy)
        # Priorytet: 1.5-flash, potem jakikolwiek inny flash
        selected = None
        for m in model_names:
            if "1.5-flash" in m:
                selected = m
                break
        
        if not selected:
            for m in model_names:
                if "flash" in m:
                    selected = m
                    break
        
        if selected:
            return genai.GenerativeModel(selected), selected
        return None, "Brak dostępnego modelu Flash"
    except Exception as e:
        return None, f"Błąd połączenia: {str(e)}"

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
    # Porządkowanie danych chronologicznie przed zapisem
    df_final['M_Idx'] = df_final['Miesiąc'].apply(lambda x: M_LIST.index(x))
    df_final = df_final.sort_values(['Rok', 'M_Idx']).drop(columns=['M_Idx'])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Zarobki')
        stats_df = df_final[['Miesiąc', 'Godziny Suma', 'Nadgodziny', 'Suma PLN']]
        stats_df.to_excel(writer, index=False, sheet_name='Statystyki')

    output.seek(0)
    wb = openpyxl.load_workbook(output)
    
    # Arkusz 1: Zarobki + Miniaturka
    ws1 = wb['Zarobki']
    if pil_image:
        row_idx = ws1.max_row
        img_temp = pil_image.copy()
        img_temp.thumbnail((1600, 2000)) # Wysoka jakość wewnątrz
        img_buf = BytesIO()
        img_temp.save(img_buf, format="PNG")
        img_xl = OpenpyxlImage(img_buf)
        img_xl.width, img_xl.height = 80, 105 # Miniaturka w widoku arkusza
        ws1.add_image(img_xl, f'I{row_idx}')
        ws1.row_dimensions[row_idx].height = 80
        ws1.column_dimensions['I'].width = 15

    # Arkusz 2: Statystyki + Wykresy
    ws2 = wb['Statystyki']
    if ws2.max_row > 1:
        # Dodajemy 3 wykresy: Godziny, Nadgodziny, PLN
        for i, title in enumerate(["Suma Godzin", "Nadgodziny", "Zarobki (PLN)"], 1):
            chart = BarChart()
            chart.title = title
            data = Reference(ws
