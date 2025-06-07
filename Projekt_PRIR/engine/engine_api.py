from flask import Flask, jsonify, request
from scraper import run_ebay_scraper 
import os

app = Flask(__name__)

@app.route('/start-scraping', methods=['POST'])
def start_scraping_endpoint():
    params = request.get_json()
    if not params or 'query' not in params:
        print("ENGINE_API: Błąd - Brakujące dane 'query' w żądaniu.")
        return jsonify({"status": "error", "message": "Brakujące dane: query"}), 400

    query = params.get('query')
    min_price = params.get('min_price', '')
    max_price = params.get('max_price', '')
    sort_order = params.get('sort_order', 'price_desc') 
    
    result_items, status_message = run_ebay_scraper(
        query, min_price, max_price, sort_order
    )
    
    response_status = "success" if "success" in status_message.lower() else "error" 
    
    return jsonify({
        "status": response_status,
        "message": status_message,
        "ads_found": len(result_items),
    }), 200 if response_status == "success" else 500

if __name__ == '__main__':
    print("ENGINE_API: Uruchamianie serwera Flask API silnika na porcie 5001")
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=5001, debug=debug_mode)