

import os
import json
import requests
import chromadb
from tqdm import tqdm

# --- CONFIGURAZIONE ---
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
ASSETS_FILE = "assets_structure.json"
DB_PATH = "icon_db"
COLLECTION_NAME = "fluent_icons"

def get_embedding(text, model=EMBEDDING_MODEL):
    """
    Ottiene l'embedding per un dato testo usando il modello specificato in Ollama.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("embedding")
    except requests.exceptions.RequestException as e:
        print(f"\nErrore di connessione a Ollama: {e}")
        return None
    except Exception as e:
        print(f"\nErrore imprevisto durante la generazione dell'embedding: {e}")
        return None

def main():
    """
    Funzione principale per creare e popolare il database vettoriale delle icone.
    """
    # 1. Verifica l'esistenza del file di assets
    if not os.path.exists(ASSETS_FILE):
        print(f"ERRORE: File '{ASSETS_FILE}' non trovato. Impossibile procedere.")
        return

    # 2. Carica i nomi delle icone
    try:
        with open(ASSETS_FILE, 'r', encoding='utf-8') as f:
            asset_structure = json.load(f)
        icon_names = list(asset_structure.keys())
        print(f"Trovati {len(icon_names)} nomi di icone in '{ASSETS_FILE}'.")
    except (json.JSONDecodeError, IOError) as e:
        print(f"ERRORE: Impossibile leggere o parsare '{ASSETS_FILE}': {e}")
        return

    # 3. Inizializza il client di ChromaDB
    print(f"Inizializzazione del database vettoriale in '{DB_PATH}'...")
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # 4. Crea o ottiene la collezione
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    print(f"Collezione '{COLLECTION_NAME}' pronta.")

    # 5. Filtra le icone già presenti nel database per evitare duplicati
    existing_ids = set(collection.get(include=[])['ids'])
    new_icons_to_index = [name for name in icon_names if name not in existing_ids]

    if not new_icons_to_index:
        print("Nessuna nuova icona da indicizzare. Il database è già aggiornato.")
        return

    print(f"Trovate {len(new_icons_to_index)} nuove icone da indicizzare.")

    # 6. Processa e indicizza le nuove icone
    embeddings = []
    documents = []
    ids = []

    print("Inizio del processo di embedding (potrebbe richiedere tempo)...")
    for icon_name in tqdm(new_icons_to_index, desc="Generazione Embeddings"):
        embedding = get_embedding(icon_name)
        if embedding:
            embeddings.append(embedding)
            documents.append(icon_name)
            ids.append(icon_name)
        else:
            print(f"Skipping icon '{icon_name}' due to embedding error.")
            
    # 7. Aggiungi i nuovi dati alla collezione in un unico batch
    if ids:
        print(f"\nAggiunta di {len(ids)} nuove icone al database...")
        try:
            collection.add(
                embeddings=embeddings,
                documents=documents,
                ids=ids
            )
            print("Database aggiornato con successo!")
        except Exception as e:
            print(f"ERRORE durante l'aggiunta dei dati al database: {e}")

    total_items = collection.count()
    print(f"\nProcesso completato. La collezione '{COLLECTION_NAME}' contiene ora {total_items} elementi.")


if __name__ == "__main__":
    main()

