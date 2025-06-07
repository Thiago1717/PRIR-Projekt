import asyncio
import aiohttp
from bs4 import BeautifulSoup
from pymongo import MongoClient, server_api
import hashlib
import os
import traceback
import re
from concurrent.futures import ProcessPoolExecutor
import random

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "scraper_db"
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0'
]

def get_mongo_client_and_db():
    try:
        client = MongoClient(MONGO_URI, server_api=server_api.ServerApi('1'), serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[DB_NAME]
        return client, db
    except Exception as e:
        print(f"BŁĄD_SCRAPERA: Błąd połączenia/operacji MongoDB: {e}")
    return None, None

async def fetch_html_content(session, url, params): 
    """Asynchronicznie pobiera zawartość HTML strony, używając losowego User-Agenta."""
    selected_user_agent = random.choice(USER_AGENTS)
    headers = {
        'User-Agent': selected_user_agent,
        'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    }
    try:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
            response.raise_for_status()
            return await response.text()
    except aiohttp.ClientError as e:
        print(f"BŁĄD_SCRAPERA (fetch_html_content): Błąd aiohttp: {url} - {e}") 
        return None
    except asyncio.TimeoutError:
        print(f"BŁĄD_SCRAPERA (fetch_html_content): Timeout: {url}") 
        return None
    except Exception as e:
        print(f"BŁĄD_SCRAPERA (fetch_html_content): Nieoczekiwany błąd: {url} - {e}") 
        return None

def parse_single_item_html(item_html_str, query_for_item):
    def _extract_price_static(price_str_val): 
        if not price_str_val: return None
        price_str_cleaned = re.sub(r'(USD|\$|PLN|zł|EUR|€|\s)', '', price_str_val, flags=re.IGNORECASE).replace(',', '.')
        try:
            cleaned_price_num_str = re.sub(r'[^\d.]', '', price_str_cleaned)
            if cleaned_price_num_str.count('.') > 1:
                parts = cleaned_price_num_str.split('.')
                cleaned_price_num_str = "".join(parts[:-1]) + "." + parts[-1]
            return float(cleaned_price_num_str) if cleaned_price_num_str else None
        except ValueError: return None

    item_soup = BeautifulSoup(item_html_str, 'html.parser')
    title_tag = item_soup.select_one(".s-item__title span[role='heading'], .s-item__title")
    title_text = title_tag.get_text(strip=True) if title_tag else None
    if title_text and "Shop on eBay" in title_text: return None
    price_tag = item_soup.select_one(".s-item__price")
    price_text = price_tag.get_text(strip=True) if price_tag else None
    link_tag = item_soup.select_one(".s-item__link")
    link_href = link_tag["href"] if link_tag and link_tag.get("href") else None
    shipping_tag = item_soup.select_one(".s-item__shipping, .s-item__logisticsCost")
    shipping_text = shipping_tag.get_text(strip=True) if shipping_tag else "N/A"
    location_tag = item_soup.select_one(".s-item__location")
    location_text = location_tag.get_text(strip=True) if location_tag else "Nieznana"

    if title_text and price_text and link_href:
        price_value = _extract_price_static(price_text)
        item_id = hashlib.md5(f"{title_text}{link_href}".encode('utf-8')).hexdigest()
        return {"_id": item_id, "title": title_text, "price_text": price_text, "price_value": price_value, 
                "shipping_info": shipping_text, "location": location_text, "link": link_href, "query_source": query_for_item}
    return None

async def parse_ebay_page_content_multiproc(html_content, query_for_items, loop, executor):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    item_elements_html_str = [str(item) for item in soup.select("li.s-item, div.s-item")]
    if not item_elements_html_str: return []
    tasks = [loop.run_in_executor(executor, parse_single_item_html, item_html, query_for_items) 
             for item_html in item_elements_html_str]
    parsed_item_results = await asyncio.gather(*tasks)
    return [item for item in parsed_item_results if item is not None]


class EbayScraper:
    def __init__(self, loop, executor):
        self.base_url = "https://www.ebay.com/sch/i.html"
        self.client, self.db = get_mongo_client_and_db()
        self.loop = loop
        self.executor = executor
        if self.db is None:
            pass 

    def _sanitize_collection_name(self, name_str):
        if not name_str: return "default_ebay_collection"
        name = name_str.replace(" ", "_").lower()
        name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
        return name[:100] if name else "default_ebay_collection"

    async def scrape_and_save(self, query, min_price, max_price, sort_order_str):
        if self.db is None: return [], "Błąd połączenia z bazą danych"

        request_params = {"_nkw": query}
        if min_price: request_params["_udlo"] = min_price
        if max_price: request_params["_udhi"] = max_price
        if sort_order_str == 'price_asc': request_params["_sop"] = "15"
        elif sort_order_str == 'price_desc': request_params["_sop"] = "2"
        
        pages_to_scrape_params = [request_params] 
        all_parsed_items = []

        async with aiohttp.ClientSession() as session:
            fetch_tasks = [fetch_html_content(session, self.base_url, page_params) 
                           for page_params in pages_to_scrape_params]
            
            html_contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            parse_tasks = []
            any_successful_fetch = False
            for content_or_exception in html_contents:
                if isinstance(content_or_exception, Exception) or content_or_exception is None:
                    continue 
                any_successful_fetch = True
                parse_tasks.append(parse_ebay_page_content_multiproc(content_or_exception, query, self.loop, self.executor))
            
            if not any_successful_fetch:
                 return [], "Nie udało się pobrać żadnej zawartości z eBay (wszystkie próby nieudane)."
            
            if parse_tasks:
                list_of_item_lists = await asyncio.gather(*parse_tasks)
                for item_list_from_page in list_of_item_lists:
                    all_parsed_items.extend(item_list_from_page)

        if not all_parsed_items:
            if any_successful_fetch:
                return [], "Nie znaleziono lub nie sparsowano żadnych ofert z pomyślnie pobranych stron eBay."
            return [], "Nie udało się pobrać żadnej zawartości z eBay lub nie znaleziono ofert."

        collection_name = self._sanitize_collection_name(query)
        collection = self.db[collection_name]
        try:
            if all_parsed_items:
                for item_data in all_parsed_items:
                    collection.update_one({"_id": item_data["_id"]}, {"$set": item_data}, upsert=True)
        except Exception as e_db:
            print(f"BŁĄD_SCRAPERA: Błąd zapisu do DB (kolekcja: {collection_name}): {e_db}")
            return all_parsed_items, f"Scrapowanie zakończone, ale wystąpił błąd zapisu do DB: {e_db}"

        return all_parsed_items, "Scrapowanie zakończone pomyślnie"
    
    def close_connection(self):
        if self.client: self.client.close()

def run_ebay_scraper(query, min_price, max_price, sort_order):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    executor = ProcessPoolExecutor() 
    
    scraper = EbayScraper(loop, executor)
    items = []
    message = "Scrapowanie nie powiodło się (błąd inicjalizacji lub nieoczekiwany błąd)"
    
    if scraper.db is None:
        message = "Baza danych niedostępna (błąd połączenia podczas inicjalizacji)."
        if scraper.client: scraper.close_connection()
        executor.shutdown(wait=False) 
        loop.close()
        return items, message

    try:
        items, message = loop.run_until_complete(scraper.scrape_and_save(query, min_price, max_price, sort_order))
    except Exception as e:
        print(f"BŁĄD_KRYTYCZNY_SCRAPERA (run_ebay_scraper): Krytyczny błąd wykonania: {e}")
        traceback.print_exc()
        message = f"Krytyczny błąd wewnętrzny podczas scrapowania: {str(e)}"
    finally:
        scraper.close_connection()
        executor.shutdown(wait=True) 
        loop.close()
    
    return items, message
