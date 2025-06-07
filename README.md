
**Autorzy:**
*   Oliwier Bogdański (21181)
*   Kacper Szponar (21306)

Zakres:
1. Aplikacja pobiera, selekcjonuje i składuje  wybranedane o narzuconym profilu z witryn internetowych.
2. Profil danych jest ustalony przez realizującego projekt. Profil danych powinien obejmować min. 4 grupy, np. adresy email, adresy korespondencyjne, schemat organizacyjny itp.
3. Program wykorzystuje wielowątkowość/wieloprocesowość. Silnik należy zrealizować we własnym zakresie wykorzystując: multiprocessing i asyncio. Przetwarzanie ma być wieloprocesowe, najlepiej z możliwością skalowania na rdzenie procesora, dalej na komputery, dalej na klastry itp.
4. Do parsowania kontentu należy użyć beautifulsoup.
5. Dane mają być zapisywane w BD, np. MongoDB
6. Program ma posiadać interfejs graficzny zrealizowany w Python (Flask lub Django) 
7. Docelowo aplikacja ma być rozproszona na min 3 moduły: interfejs (1 lub więcej kontenerów), silnik (1 kontener), BD (1 kontener). Sposób ulokowania należy opracować we własnym zakresie i potrafić uzasadnić wybory.
8. Oprogramowanie może być zrealizowane w grupie 1 lub 2 osobowej. 
9. Projekt uznaje się za złożony, jeżeli w wyznaczonym terminie zostanie opublikowany szczegółowy raport z dowiązaniem do repozytorium kodu (github) oraz zostanie zademonstrowany prowadzącemu na ostatnich zajęciach laboratoryjnych.

---

## Struktura Projektu
Projekt_PRIR/                     
├── Dockerfile               
├── docker-compose.yml    
|    
├── engine/                   
│   ├── Dockerfile            
│   ├── requirements.txt      
│   ├── engine_api.py         
│   └── scraper.py             
│
├── flask_app/                
│   ├── Dockerfile            
│   ├── requirements.txt      
│   ├── app.py                
│   ├── static/               
│   │   └── css/
│   │       ├── style_index.css
│   │       └── style_results.css
│   └── templates/            
│       ├── index.html
│       └── results.html
   
