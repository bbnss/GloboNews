import chromadb

DB_PATH = "icon_db"
COLLECTION_NAME = "fluent_icons"

def view_db_content():
    try:
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        
        print(f"Contenuto della collezione '{COLLECTION_NAME}' ({collection.count()} elementi):\n")
        
        # Recupera tutti gli elementi (solo ID e documenti, non embeddings per leggibilità)
        results = collection.get(ids=collection.get(include=[])['ids'], include=['documents'])
        
        if not results['ids']:
            print("La collezione è vuota.")
            return
            
        for i in range(len(results['ids'])):
            print(f"ID: {results['ids'][i]}, Document: {results['documents'][i]}")
            
    except Exception as e:
        print(f"Errore durante la lettura del database: {e}")

if __name__ == "__main__":
    view_db_content()