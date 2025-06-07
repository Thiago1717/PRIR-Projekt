from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient, ASCENDING, DESCENDING 
import requests
import os
import re 

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "scraper_db" 
ENGINE_API_URL = os.environ.get("ENGINE_URL", "http://engine_app:5001/start-scraping")

def get_db_client():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"FLASK_UI: Błąd połączenia z MongoDB: {e}")
        return None

def sanitize_collection_name_for_ui(name):
    if not name:
        return "default_ebay_collection"
    name = name.replace(" ", "_").lower()
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name) 
    if not name:
        name = "default_ebay_collection"
    return name[:100]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/trigger-scrape', methods=['POST'])
def trigger_scrape():
    params = request.get_json() 
    if not params or 'query' not in params or not params.get('query').strip():
        return jsonify({"status": "error", "message": "Brakujące lub puste dane: query"}), 400
    
    query = params.get('query')
    min_price_str = params.get('min_price', '')
    max_price_str = params.get('max_price', '')
    sort_order = params.get('sort_order', 'price_desc') 

    if min_price_str and max_price_str:
        try:
            min_price_val = float(min_price_str)
            max_price_val = float(max_price_str)
            if min_price_val < 0 or max_price_val < 0:
                 return jsonify({"status": "error", "message": "Ceny nie mogą być ujemne."}), 400
            if min_price_val > max_price_val:
                return jsonify({"status": "error", "message": "Cena minimalna nie może być wyższa niż cena maksymalna."}), 400
        except ValueError:
            return jsonify({"status": "error", "message": "Nieprawidłowy format ceny. Proszę podać liczby."}), 400
    elif min_price_str:
        try:
            if float(min_price_str) < 0:
                return jsonify({"status": "error", "message": "Cena minimalna nie może być ujemna."}), 400
        except ValueError:
            return jsonify({"status": "error", "message": "Nieprawidłowy format ceny minimalnej."}), 400
    elif max_price_str:
        try:
            if float(max_price_str) < 0:
                return jsonify({"status": "error", "message": "Cena maksymalna nie może być ujemna."}), 400
        except ValueError:
            return jsonify({"status": "error", "message": "Nieprawidłowy format ceny maksymalnej."}), 400

    engine_params = {
        'query': query,
        'min_price': str(min_price_str) if min_price_str else '',
        'max_price': str(max_price_str) if max_price_str else '',
        'sort_order': sort_order 
    }
    
    try:
        response = requests.post(ENGINE_API_URL, json=engine_params, timeout=300)
        response.raise_for_status() 
        return jsonify(response.json()), response.status_code
    except requests.exceptions.Timeout:
        msg = "FLASK_UI: Błąd: Przekroczono czas oczekiwania na odpowiedź od silnika."
        print(msg)
        return jsonify({"status": "error", "message": msg}), 504
    except requests.exceptions.ConnectionError:
        msg = "FLASK_UI: Błąd: Nie można połączyć się z silnikiem scrapującym."
        print(msg)
        return jsonify({"status": "error", "message": msg}), 503
    except requests.exceptions.HTTPError as e:
        msg = f"FLASK_UI: Błąd HTTP od silnika: {e.response.status_code}"
        print(f"{msg} - Odpowiedź: {e.response.text}") 
        try:
            return jsonify(e.response.json()), e.response.status_code
        except ValueError: 
            return jsonify({"status": "error", "message": f"{msg} - {e.response.text}"}), e.response.status_code
    except Exception as e:
        msg = f"FLASK_UI: Nieoczekiwany błąd podczas komunikacji z silnikiem: {str(e)}"
        print(msg)
        return jsonify({"status": "error", "message": msg}), 500

@app.route('/results')
def show_results():
    query_param_original = request.args.get('query', None)
    sort_param = request.args.get('sort', 'price_asc') 

    ads_list = []
    db_error = False
    collection_name_display = query_param_original if query_param_original else "N/A (proszę najpierw wyszukać)"

    mongo_client_ui = get_db_client()
    if mongo_client_ui:
        db_ui = mongo_client_ui[DB_NAME]
        if query_param_original:
            collection_name_to_read = sanitize_collection_name_for_ui(query_param_original)
            
            if collection_name_to_read in db_ui.list_collection_names():
                collection = db_ui[collection_name_to_read]
                
                if sort_param == 'price_desc':
                    sort_direction = DESCENDING
                else: 
                    sort_direction = ASCENDING
                ads_list = list(collection.find({}).sort([("price_value", sort_direction), ("_id", ASCENDING)]))
        
        if mongo_client_ui:
            mongo_client_ui.close()
    else:
        db_error = True
        
    return render_template('results.html', ads=ads_list, db_error=db_error, query=collection_name_display)

if __name__ == '__main__':
    is_debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    print(f"FLASK_UI: Uruchamianie serwera Flask UI na porcie 5000 (Debug: {is_debug_mode})")
    app.run(host='0.0.0.0', port=5000, debug=is_debug_mode)