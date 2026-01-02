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
    st.header
