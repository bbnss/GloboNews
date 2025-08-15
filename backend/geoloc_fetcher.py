import chromadb
import re
import json
import requests
import feedparser
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime
import urllib.parse
import random
import subprocess
from dotenv import load_dotenv

# --- CARICAMENTO VARIABILI D'AMBIENTE ---
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH_NAME")
REPO_LOCAL_PATH = "GloboNews_repo" # Nome della cartella locale per il clone

# --- CONFIGURAZIONE ---
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3n:e2b"
EMBEDDING_MODEL = "nomic-embed-text"
USER_AGENT = "NotizIA-App/1.0"
ASSETS_FILE = "assets_structure.json"
DEFAULT_ICON = "Newspaper"
DB_PATH = "icon_db"
COLLECTION_NAME = "fluent_icons"
# Modifica: Il manifest ora si trova nel repo clonato
MANIFEST_FILE = os.path.join(REPO_LOCAL_PATH, "public/news_manifest.json")
SOURCE_TRACKER_FILE = "source_tracker.json"
PROCESSED_NEWS_TRACKER_FILE = "processed_news_tracker.json"

# --- CARICAMENTO RISORSE E CONNESSIONE DB ---
try:
    with open(ASSETS_FILE, 'r', encoding='utf-8') as f:
        ASSET_STRUCTURE = json.load(f)
    ICON_NAMES = list(ASSET_STRUCTURE.keys())
    print(f"Caricata struttura di {len(ICON_NAMES)} icone da '{ASSETS_FILE}'.")
except FileNotFoundError:
    print(f"ERRORE: File '{ASSETS_FILE}' non trovato. Impossibile procedere.")
    ASSET_STRUCTURE = {}
    ICON_NAMES = []
except json.JSONDecodeError:
    print(f"ERRORE: Formato JSON non valido in '{ASSETS_FILE}'.")
    ASSET_STRUCTURE = {}
    ICON_NAMES = []

try:
    client = chromadb.PersistentClient(path=DB_PATH)
    ICON_COLLECTION = client.get_collection(name=COLLECTION_NAME)
    print(f"Connesso alla collezione '{COLLECTION_NAME}' con {ICON_COLLECTION.count()} elementi.")
except Exception as e:
    print(f"ERRORE: Impossibile connettersi al database vettoriale: {e}")
    ICON_COLLECTION = None


def call_llm(prompt, format="json", max_retries=3, retry_delay=5):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": format},
                timeout=300
            )
            response.raise_for_status()
            response_text = response.json().get("response", "{}")
            return response_text, None
        except requests.exceptions.RequestException as e:
            error_msg = f"Errore di connessione a Ollama (generativo) [Tentativo {attempt + 1}/{max_retries}]: {e}"
            if attempt < max_retries - 1:
                print(f"  - {error_msg}. Riprovo in {retry_delay} secondi...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return None, error_msg
        except Exception as e:
            error_msg = f"Errore imprevisto nella chiamata LLM (generativo): {e}"
            return None, error_msg

def get_embedding(text, max_retries=3, retry_delay=5):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text},
                timeout=300
            )
            response.raise_for_status()
            return response.json().get("embedding"), None
        except requests.exceptions.RequestException as e:
            error_msg = f"Errore di connessione a Ollama (embedding) [Tentativo {attempt + 1}/{max_retries}]: {e}"
            if attempt < max_retries - 1:
                print(f"\nAttenzione: {error_msg}. Riprovo in {retry_delay} secondi...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return None, f"Fallito recupero embedding dopo {max_retries} tentativi: {e}"
        except Exception as e:
            return None, f"Errore imprevisto durante la generazione dell'embedding: {e}"


def get_keywords_from_article(article):
    prompt = f"""
    Analizza il seguente testo e identifica il suo **tema visivo centrale**.
    
    **Processo:**
    1.  Qual è l'oggetto, il concetto o l'emozione più importante della notizia?
    2.  Se la notizia parla di un incidente in bicicletta, il tema è "bicicletta".
    3.  Se parla di una crisi finanziaria, il tema è "denaro" o "grafico in perdita".
    4.  Se parla di una discussione tra due persone, il tema è più astratto, forse "dibattito" o "conflitto".
    
    Estrai da 3 a 5 parole chiave in INGLESE che descrivano questo tema. La prima parola chiave deve essere la più importante e concreta possibile.
    
    Restituisci solo un array JSON. Esempio: {{"keywords": ["bicycle", "accident", "road", "injury"]}}
    
    Testo: "{article['title']}. {article['content']}"
    """
    response_str, error = call_llm(prompt)
    if error:
        return [], error
    try:
        return json.loads(response_str).get("keywords", []), None
    except json.JSONDecodeError:
        return [], f"Errore nel parsing JSON delle parole chiave: {response_str}"

def find_best_icon_vector_search(keywords):
    if not ICON_COLLECTION or not keywords:
        return DEFAULT_ICON, "Database non disponibile o nessuna parola chiave."

    query_text = ", ".join(keywords)
    query_embedding, error = get_embedding(query_text)

    if error:
        return DEFAULT_ICON, error

    try:
        results = ICON_COLLECTION.query(
            query_embeddings=[query_embedding],
            n_results=1
        )
        if results and results['ids'] and results['ids'][0]:
            return results['ids'][0][0], None
        else:
            return DEFAULT_ICON, "Nessun risultato dalla ricerca vettoriale."
    except Exception as e:
        return DEFAULT_ICON, f"Errore durante la query al DB vettoriale: {e}"


def get_geolocation_for_article(article):
    prompt = f"""
Sei un analista geografo esperto per un'agenzia di stampa mondiale. Il tuo unico compito è leggere una notizia e posizionarla correttamente su una mappa.

**Processo da seguire:**
1.  **Analisi del Contesto:** Leggi l'intero articolo per capire qual è il suo messaggio centrale. Non fermarti alle parole chiave.
2.  **Individuazione del Fulcro:** Identifica il "fulcro geografico" della notizia. Dove si concentra l'azione? Dove avvengono i fatti più importanti?
3.  **Scarta le Menzioni Periferiche:** Se la notizia parla di una crisi a Gaza e il presidente del Brasile commenta, il fulcro è **Gaza**, non il Brasile. Scarta attivamente le località non centrali.
4.  **Formulazione della Risposta:** Basandoti sulla tua analisi, compila il seguente JSON. Non aggiungere nient'altro alla tua risposta.

**Formato di output (solo JSON):**
{{
  "city": "Nome della città (se applicabile)",
  "region": "Nome della regione/stato (se applicabile)",
  "country": "Nome della nazione (in inglese, obbligatorio)",
  "reasoning": "Una frase che spiega perché questa è la località centrale della notizia."
}}

**Testo della notizia da analizzare:**
{article['title']}. {article['content']}
"""
    response_str, error = call_llm(prompt, format="json") # Assicuriamoci che il formato sia json
    if error:
        return None, error # Restituisce None e l'errore

    try:
        # Parsa l'intera risposta JSON
        data = json.loads(response_str)
        
        city = data.get("city", "")
        region = data.get("region", "")
        country = data.get("country", "")
        
        # Costruisce il nome della località in ordine di specificità
        location_parts = [part for part in [city, region, country] if part]
        location_name = ", ".join(location_parts)
        
        # Se non c'è un paese, consideriamo la geolocalizzazione fallita
        if not country:
            return "N/A", "Nessuna nazione identificata dal LLM."
            
        return location_name, None
    except (json.JSONDecodeError, KeyError) as e:
        return "N/A", f"Errore nel parsing JSON o chiave mancante: {e} | Risposta ricevuta: {response_str}"


def get_coordinates(location_name):
    if not location_name or location_name == "N/A":
        return None, None
    try:
        headers = {'User-Agent': USER_AGENT}
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_name)}&format=json&limit=1"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return (float(data[0]["lat"]), float(data[0]["lon"])) if data else (None, None)
    except Exception:
        return None, None

def build_icon_url(icon_name):
    if not icon_name:
        return None

    base_url = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets"
    correct_folder_name = next((name for name in ICON_NAMES if name.lower() == icon_name.lower()), None)
    if not correct_folder_name:
        return build_icon_url(DEFAULT_ICON)

    icon_data = ASSET_STRUCTURE.get(correct_folder_name, {})
    asset_filename = None
    asset_type_folder = None

    search_order = [("3D", "_3d.png"), ("3D", "_3d.svg"), ("Color", "_color.png"), ("Color", "_color.svg")]
    
    for folder, suffix in search_order:
        if "Default" in icon_data and folder in icon_data["Default"] and icon_data["Default"][folder].get("files"):
            for f in icon_data["Default"][folder]["files"]:
                if f.endswith(suffix):
                    asset_filename = f
                    asset_type_folder = folder
                    break
        if asset_filename: break
        
        if folder in icon_data and icon_data[folder].get("files"):
            for f in icon_data[folder]["files"]:
                if f.endswith(suffix):
                    asset_filename = f
                    asset_type_folder = folder
                    break
        if asset_filename: break

    if not asset_filename:
        return build_icon_url(DEFAULT_ICON)

    encoded_folder_name = urllib.parse.quote(correct_folder_name)
    
    if "Default" in icon_data:
         return f"{base_url}/{encoded_folder_name}/Default/{asset_type_folder}/{asset_filename}"
    else:
         return f"{base_url}/{encoded_folder_name}/{asset_type_folder}/{asset_filename}"


def read_rss_feeds_from_file(file_path):
    """Legge un file di testo che contiene un dizionario di feed RSS."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Assumiamo che il file contenga "chiave": "valore", ...
            rss_feeds = json.loads(f"{{{content}}}")
            return rss_feeds
    except FileNotFoundError:
        print(f"Errore: File delle fonti '{file_path}' non trovato.")
        return {}
    except json.JSONDecodeError:
        print(f"Errore: Formato JSON non valido in '{file_path}'.")
        return {}

def get_news_from_rss(rss_feeds):
    news = []
    print("Inizio download notizie...")
    for source, url in rss_feeds.items():
        print(f"  - Scaricando da: {source} ({url})")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                soup = BeautifulSoup(getattr(entry, 'summary', ''), 'html.parser')
                content = soup.get_text(separator=' ', strip=True)
                timestamp = "Data non disponibile"
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', entry.published_parsed)
                news.append({
                    'source': source,
                    'title': getattr(entry, 'title', 'Senza titolo'),
                    'link': getattr(entry, 'link', ''),
                    'content': content.split("L'articolo")[0].strip(),
                    'timestamp': timestamp
                })
        except Exception as e:
            print(f"    ! Errore durante il download da {source}: {e}")
    print(f"Download completato. Totale notizie: {len(news)}")
    return news

def write_markdown_file(news_list, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        for item in news_list:
            f.write(f"## [{item['title']}]({item['link']})\n")
            f.write(f"**Data:** {item['timestamp']}\n**Fonte:** {item['source']}\n\n{item['content']}\n\n---\n\n")

def create_report(stats, output_dir):
    """Crea un file di report con le statistiche dell'esecuzione."""
    duration = stats['end_time'] - stats['start_time']
    report_content = f"""
# Report di Esecuzione NotizIA
- Ora di inizio: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
- Ora di fine: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}
- Durata totale: {str(duration)}
---
## Statistiche Notizie
- **Fonte processata:** {stats.get('source_name', 'N/D')}
- Notizie totali scaricate dal feed: {stats['total_news']}
- Notizie nuove (non ancora processate): {stats['new_news']}
- Notizie geolocalizzate con successo: {stats['geoloc_success']}
- Notizie fallite (geolocalizzazione): {stats['geoloc_failed']}
---
## Statistiche Icone
- Icone trovate con successo: {stats['icon_success']}
- Icone non trovate (usato fallback): {stats['icon_failed']}
"""
    with open(os.path.join(output_dir, "report.txt"), 'w', encoding='utf-8') as f:
        f.write(report_content)

def update_manifest():
    """
    Scansiona la directory public/data nel repository clonato, genera un nuovo manifest
    con i file JSON esistenti, lo ordina e lo limita.
    """
    print("Ricostruzione del manifest dai file esistenti...")
    data_dir = os.path.join(REPO_LOCAL_PATH, "public/data")
    
    if not os.path.exists(data_dir):
        print(f"La directory dei dati '{data_dir}' non esiste. Manifest non creato.")
        return

    # Trova tutti i file JSON nelle sottocartelle (che sono le timestamp)
    all_news_files = []
    for dirname in os.listdir(data_dir):
        dirpath = os.path.join(data_dir, dirname)
        if os.path.isdir(dirpath):
            for filename in os.listdir(dirpath):
                if filename.endswith(".json"):
                    # Salva il percorso relativo, es: "data/2025-08-08.../file.json"
                    relative_path = os.path.join("data", dirname, filename)
                    all_news_files.append(relative_path)

    # Ordina i file dal più recente al più vecchio basandosi sul nome della cartella
    all_news_files.sort(key=lambda x: os.path.basename(os.path.dirname(x)), reverse=True)

    # Limita il numero di voci nel manifest
    max_entries = 100
    manifest = all_news_files[:max_entries]

    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        
    print(f"Manifest ricostruito e salvato con {len(manifest)} voci.")

def manage_source_tracker():
    all_sources = read_rss_feeds_from_file("fonti.txt")
    if not all_sources:
        return None, None

    tracker = {"unprocessed": [], "processed": []}
    if os.path.exists(SOURCE_TRACKER_FILE):
        with open(SOURCE_TRACKER_FILE, 'r', encoding='utf-8') as f:
            try:
                tracker = json.load(f)
            except json.JSONDecodeError:
                print("Tracker delle fonti corrotto, ne verrà creato uno nuovo.")

    if not tracker["unprocessed"]:
        print("Tutte le fonti processate. Inizio un nuovo ciclo casuale.")
        unprocessed_sources = list(all_sources.keys())
        random.shuffle(unprocessed_sources)
        tracker["unprocessed"] = unprocessed_sources
        tracker["processed"] = []
        with open(SOURCE_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(tracker, f, indent=2)
        print("Nuovo ciclo salvato nel tracker.")

    source_to_process_name = tracker["unprocessed"][0]
    source_to_process_url = all_sources.get(source_to_process_name)
    
    if not source_to_process_url:
        print(f"Attenzione: la fonte '{source_to_process_name}' non è più presente in fonti.txt. La rimuovo dal ciclo.")
        tracker["unprocessed"].remove(source_to_process_name)
        with open(SOURCE_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(tracker, f, indent=2)
        return manage_source_tracker() # Riprova con la prossima fonte

    return {source_to_process_name: source_to_process_url}, source_to_process_name

def update_source_tracker(processed_source_name):
    tracker = {"unprocessed": [], "processed": []}
    if os.path.exists(SOURCE_TRACKER_FILE):
        with open(SOURCE_TRACKER_FILE, 'r', encoding='utf-8') as f:
            tracker = json.load(f)

    if processed_source_name in tracker["unprocessed"]:
        tracker["unprocessed"].remove(processed_source_name)
        tracker["processed"].append(processed_source_name)

    with open(SOURCE_TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(tracker, f, indent=2)
    print(f"Fonte '{processed_source_name}' segnata come processata.")


# --- FUNZIONI GIT ---
def run_git_command(command, cwd):
    """Esegue un comando git nella directory specificata e gestisce gli errori."""
    try:
        print(f"Eseguendo: git {' '.join(command)} in '{cwd}'")
        result = subprocess.run(['git'] + command, cwd=cwd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERRORE durante l'esecuzione di git {' '.join(command)}:")
        print("Exit Code:", e.returncode)
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    except FileNotFoundError:
        print("ERRORE: 'git' non è installato o non è nel PATH.")
        return False

def setup_git_repository():
    """Clona il repository se non esiste, altrimenti fa il pull."""
    if not all([GITHUB_REPO_URL, GITHUB_BRANCH, GITHUB_TOKEN]):
        print("ERRORE: Le variabili d'ambiente GitHub non sono configurate correttamente.")
        return False

    if os.path.exists(REPO_LOCAL_PATH):
        print(f"La cartella '{REPO_LOCAL_PATH}' esiste. Eseguo il pull...")
        if not run_git_command(['pull', 'origin', GITHUB_BRANCH], cwd=REPO_LOCAL_PATH):
            return False
    else:
        print(f"Clonazione del repository in '{REPO_LOCAL_PATH}'...")
        # Inserisce il token nell'URL per l'autenticazione
        auth_url = GITHUB_REPO_URL.replace("https://", f"https://oauth2:{GITHUB_TOKEN}@")
        if not run_git_command(['clone', '--branch', GITHUB_BRANCH, auth_url, REPO_LOCAL_PATH], cwd="."):
            return False
    return True

def commit_and_push_changes():
    """Aggiunge, committa e pusha le modifiche al repository GitHub."""
    print("Avvio del processo di commit e push su GitHub...")
    
    # Configura utente git per il commit
    run_git_command(['config', 'user.name', 'NotizIA Bot'], cwd=REPO_LOCAL_PATH)
    run_git_command(['config', 'user.email', 'bot@notizia.com'], cwd=REPO_LOCAL_PATH)

    if not run_git_command(['add', '.'], cwd=REPO_LOCAL_PATH):
        return
    
    # Controlla se ci sono modifiche da committare
    status_result = subprocess.run(['git', 'status', '--porcelain'], cwd=REPO_LOCAL_PATH, capture_output=True, text=True)
    if not status_result.stdout:
        print("Nessuna modifica da committare.")
        return

    commit_message = f"BOT: Aggiornamento notizie del {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if not run_git_command(['commit', '-m', commit_message], cwd=REPO_LOCAL_PATH):
        return
    
    if not run_git_command(['push', 'origin', GITHUB_BRANCH], cwd=REPO_LOCAL_PATH):
        return
    
    print("Push completato con successo!")

if __name__ == "__main__":
    if not ASSET_STRUCTURE or not ICON_COLLECTION:
        print("Uscita a causa di errori nel caricamento delle risorse o nella connessione al DB.")
        exit()

    if not setup_git_repository():
        print("Impossibile sincronizzare il repository Git. Uscita.")
        exit()

    start_time = datetime.now()
    
    processed_news_links = set()
    if os.path.exists(PROCESSED_NEWS_TRACKER_FILE):
        with open(PROCESSED_NEWS_TRACKER_FILE, 'r', encoding='utf-8') as f:
            try:
                processed_news_links = set(json.load(f))
            except json.JSONDecodeError:
                print("Attenzione: file tracker delle notizie processate corrotto.")

    source_to_process, source_name = manage_source_tracker()
    
    if not source_to_process:
        print("Nessuna fonte RSS da processare. Uscita.")
    else:
        print(f"\n--- Inizio processamento per la fonte: {source_name} ---")
        
        articles_from_rss = get_news_from_rss(source_to_process)
        
        articles = [a for a in articles_from_rss if a['link'] not in processed_news_links]
        print(f"Trovate {len(articles)} nuove notizie da processare.")

        if not articles:
            print(f"Nessuna notizia nuova per {source_name}.")
            update_source_tracker(source_name)
        else:
            # Le directory di output locali rimangono per i log
            backend_output_dir = os.path.join("outputs", start_time.strftime('%Y-%m-%d_%H-%M-%S'))
            os.makedirs(backend_output_dir, exist_ok=True)

            # La directory pubblica ora punta al repo clonato
            public_repo_dir = os.path.join(REPO_LOCAL_PATH, "public/data", start_time.strftime('%Y-%m-%d_%H-%M-%S'))
            os.makedirs(public_repo_dir, exist_ok=True)

            write_markdown_file(articles, os.path.join(backend_output_dir, "notizie.md"))

            geolocated_news = []
            failed_articles = []
            log_entries = []
            icon_success_count = 0
            
            print("\nInizio processo di analisi...")
            for i, article in enumerate(articles, 1):
                title = article['title']
                print(f"\n--- Analizzando {i}/{len(articles)}: {title[:60]}... ---")
                log_line = f"NOTIZIA: {title}\n"
                
                location_name, geo_error = get_geolocation_for_article(article)
                lat, lon = get_coordinates(location_name)
                keywords, kw_error = get_keywords_from_article(article)
                final_icon_name, icon_error = find_best_icon_vector_search(keywords)
                icon_url = build_icon_url(final_icon_name)

                log_entries.append(f"{log_line}  - Geoloc: {location_name}\n  - Icona: {final_icon_name}\n---\n")

                if lat and lon:
                    if final_icon_name != DEFAULT_ICON: icon_success_count += 1
                    geolocated_news.append({
                        "lat": lat, "lon": lon, "title": title,
                        "link": article["link"], "source": article["source"],
                        "timestamp": article["timestamp"], "icon_url": icon_url,
                        "description": article.get('content', '')[:150] # Aggiunge descrizione
                    })
                else:
                    failed_articles.append(article)
            
            if geolocated_news:
                geolocated_filename = "notizie_geolocalizzate.json"
                geolocated_path = os.path.join(public_repo_dir, geolocated_filename)
                with open(geolocated_path, 'w', encoding='utf-8') as f:
                    json.dump(geolocated_news, f, indent=2, ensure_ascii=False)
                
                update_manifest()
                
                # Esegui il commit e push solo se sono state create nuove notizie
                commit_and_push_changes()
            else:
                print("Nessuna notizia geolocalizzabile, nessun push su GitHub.")

            if failed_articles:
                write_markdown_file(failed_articles, os.path.join(backend_output_dir, "notizie_da_revisionare.md"))
            
            with open(os.path.join(backend_output_dir, "geoloc_log.txt"), 'w', encoding='utf-8') as f:
                f.writelines(log_entries)
                
            stats = {
                'start_time': start_time, 'end_time': datetime.now(), 'source_name': source_name,
                'total_news': len(articles_from_rss), 'new_news': len(articles),
                'geoloc_success': len(geolocated_news), 'geoloc_failed': len(failed_articles),
                'icon_success': icon_success_count, 'icon_failed': len(articles) - icon_success_count
            }
            create_report(stats, backend_output_dir)
            
            processed_news_links.update({a['link'] for a in articles})
            with open(PROCESSED_NEWS_TRACKER_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(processed_news_links), f, indent=2)

            update_source_tracker(source_name)

            print("\n--- Processo completato ---")