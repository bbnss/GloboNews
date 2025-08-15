import re
import json
import requests

def parse_markdown(file_path):
    """
    Analizza il file markdown e restituisce una lista di notizie.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return [] # Se il file non esiste, restituisce una lista vuota

    articles = []
    news_items = content.strip().split('---')

    for item in news_items:
        if not item.strip():
            continue

        title_match = re.search(r"## \[(.*?)\]\((.*?)\)", item)
        date_match = re.search(r"\*\*Data:\*\* (.*?)\n", item)
        source_match = re.search(r"\*\*Fonte:\*\* (.*?)\n\n", item)
        content_search = re.search(r"\*\*Fonte:\*\* .*\n\n(.*)", item, re.DOTALL)

        if title_match and date_match and source_match and content_search:
            title = title_match.group(1).strip()
            link = title_match.group(2).strip()
            timestamp = date_match.group(1).strip()
            source = source_match.group(1).strip()
            news_content = content_search.group(1).strip().split("L'articolo")[0].strip()
            
            articles.append({
                "title": title, "link": link, "timestamp": timestamp,
                "source": source, "content": news_content
            })
    return articles

def review_and_geolocate(article, model="gemma3n:e4b"):
    """
    Usa un prompt "Chain of Thought" per analizzare e geolocalizzare notizie complesse.
    """
    prompt = f"""
    Analizza attentamente il testo seguente.
    1. Nel campo "thinking", descrivi il tuo processo di pensiero per trovare la località geografica. Considera ogni indizio.
    2. Nel campo "location", scrivi il nome della località che hai identificato.

    Rispondi ESCLUSIVAMENTE in formato JSON. Esempio:
    {{"thinking": "Il testo menziona un evento successo a Ibiza, che è un'isola della Spagna. Questa è la località principale.", "location": "Ibiza, Spagna"}}

    Se non trovi assolutamente nessuna località, rispondi:
    {{"thinking": "Ho analizzato il testo ma non ho trovato riferimenti geografici.", "location": "N/A"}}

    Testo:
    "{article['title']}. {article['content']}"
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"}
        )
        response.raise_for_status()
        model_response_str = response.json().get("response", "{}")
        
        location_data = json.loads(model_response_str)
        location_name = location_data.get("location", "N/A").strip()

        if location_name != "N/A" and location_name:
            lat, lon = get_coordinates(location_name)
            return lat, lon, model_response_str
        else:
            return None, None, model_response_str

    except requests.exceptions.RequestException as e:
        error_msg = f"Errore durante la chiamata a Ollama: {e}"
        print(error_msg)
        return None, None, error_msg
    except json.JSONDecodeError:
        error_msg = f"Errore: La risposta del modello non era un JSON valido: {model_response_str}"
        print(error_msg)
        return None, None, error_msg

def get_coordinates(location_name):
    """
    Converte un nome di località in coordinate.
    """
    try:
        headers = {'User-Agent': 'NotizIA-App/1.0'}
        url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        else:
            print(f"Coordinate non trovate per: {location_name}")
            return None, None
    except Exception as e:
        print(f"Errore durante la geocodifica: {e}")
        return None, None

if __name__ == "__main__":
    review_file = "notizie_da_revisionare.md"
    geolocated_output_file = "notizie_geolocalizzate.json"
    log_file = "review_log.txt"
    
    articles_to_review = parse_markdown(review_file)
    
    if not articles_to_review:
        print(f"Nessuna notizia da revisionare in '{review_file}'.")
    else:
        # Carica le notizie già geolocalizzate per aggiungerne di nuove
        try:
            with open(geolocated_output_file, 'r', encoding='utf-8') as f:
                geolocated_news = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            geolocated_news = []

        newly_geolocated_count = 0
        log_entries = []

        for article in articles_to_review:
            print(f"Revisionando: {article['title']}...")
            lat, lon, model_response = review_and_geolocate(article)
            
            log_entries.append(f"Notizia: {article['title']}\nRisposta LLM: {model_response}\n---\n")

            if lat is not None and lon is not None:
                print(f"Successo! Località trovata: {model_response}")
                geolocated_news.append({
                    "lat": lat, "lon": lon, "title": article["title"],
                    "link": article["link"], "source": article["source"],
                    "timestamp": article["timestamp"]
                })
                newly_geolocated_count += 1
            else:
                print(f"Revisione fallita per: {article['title']}")

        # Aggiorna il file JSON con le notizie geolocalizzate
        with open(geolocated_output_file, 'w', encoding='utf-8') as f:
            json.dump(geolocated_news, f, indent=2, ensure_ascii=False)
        
        print(f"\nAggiunte {newly_geolocated_count} nuove notizie a '{geolocated_output_file}'.")

        # Scrive il file di log della revisione
        with open(log_file, 'w', encoding='utf-8') as f:
            f.writelines(log_entries)
        print(f"File di log '{log_file}' creato.")

        # Opzionale: svuota il file delle notizie da revisionare se sono state processate
        # with open(review_file, 'w').close():
        #     print(f"File '{review_file}' svuotato.")
