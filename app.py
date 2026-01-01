import streamlit as st
import easyocr
import numpy as np
import holidays
import calendar
from datetime import date
from PIL import Image

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['pl'])

reader = load_ocr()

# --- ZAKŁADKA SKANOWANIA ---
tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

with tab3:
    st.subheader("Inteligentne skanowanie grafiku")
    st.info(f"Analizuję grafik dla: **{wybrany_m_nazwa} {wybrany_rok}**")
    
    plik_foto = st.file_uploader("Wgraj zdjęcie (dni 1-31 w pionie, kolumna 'Ilość godzin'):", type=['jpg', 'jpeg', 'png'])
    
    if plik_foto:
        image = Image.open(plik_foto)
        img_array = np.array(image)
        st.image(image, caption="Twój grafik", width=400)
        
        if st.button("🚀 Analizuj i rozlicz godziny"):
            with st.spinner("Przetwarzanie obrazu i kalendarza..."):
                wynik = reader.readtext(img_array)
                
                # 1. Znajdź pozycję nagłówka "ilość godzin"
                header_x = None
                for (bbox, tekst, prob) in wynik:
                    t = tekst.lower()
                    if "ilo" in t or "godz" in t:
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        break

                if not header_x:
                    st.error("Nie znalazłem nagłówka 'Ilość godzin'. Upewnij się, że jest wyraźny.")
                else:
                    # 2. Zbierz wszystkie liczby w tej kolumnie wraz z ich pozycją Y
                    data_points = []
                    for (bbox, tekst, prob) in wynik:
                        czysty_tekst = "".join(filter(str.isdigit, tekst))
                        if czysty_tekst:
                            val = int(czysty_tekst)
                            x_center = (bbox[0][0] + bbox[1][0]) / 2
                            y_center = (bbox[0][1] + bbox[2][1]) / 2
                            
                            if abs(x_center - header_x) < 60: # Margines kolumny
                                if 1 <= val <= 24: # Filtrujemy sensowne godziny
                                    data_points.append({'y': y_center, 'val': val})

                    # Sortujemy odczyty od góry do dołu (wg osi Y)
                    data_points.sort(key=lambda x: x['y'])
                    
                    # 3. Przypisz odczyty do dni miesiąca (1, 2, 3...)
                    # Zakładamy, że pierwszy odczyt to dzień 1, drugi to 2 itd.
                    # Dla pewności sprawdzamy ile dni ma dany miesiąc
                    dni_w_miesiacu = calendar.monthrange(wybrany_rok, m_idx)[1]
                    pl_holidays = holidays.Poland(years=wybrany_rok)
                    
                    wyniki_dni = {
                        "standardowe": 0.0,
                        "nadgodziny": 0.0,
                        "soboty": 0.0,
                        "niedziele_swieta": 0.0
                    }

                    for i, point in enumerate(data_points[:dni_w_miesiacu]):
                        dzien_nr = i + 1
                        h = float(point['val'])
                        curr_date = date(wybrany_rok, m_idx, dzien_nr)
                        weekday = curr_date.weekday() # 0=Pon, 5=Sob, 6=Nie
                        
                        # LOGIKA ROZLICZANIA:
                        if weekday == 5: # Sobota
                            wyniki_dni["soboty"] += h
                        elif weekday == 6 or curr_date in pl_holidays: # Niedziela lub Święto
                            wyniki_dni["niedziele_swieta"] += h
                        else: # Dzień roboczy
                            if h > 8:
                                wyniki_dni["standardowe"] += 8
                                wyniki_dni["nadgodziny"] += (h - 8)
                            else:
                                wyniki_dni["standardowe"] += h

                    # 4. Wyświetlenie wyników
                    st.success("Analiza zakończona!")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Standard", wyniki_dni["standardowe"])
                    c2.metric("Nadgodziny", wyniki_dni["nadgodziny"])
                    c3.metric("Soboty", wyniki_dni["soboty"])
                    c4.metric("Nd/Święta", wyniki_dni["niedziele_swieta"])
                    
                    st.session_state['scanned_hours'] = wyniki_dni
                    st.info("💡 Dane zostały przygotowane. Możesz teraz wrócić do pierwszej zakładki.")
