# Progetto GloboNews 🇮🇹

GloboNews è un aggregatore di notizie sperimentale che utilizza l'intelligenza artificiale per analizzare, geolocalizzare e arricchire le notizie italiane con icone rappresentative. Il progetto è progettato per funzionare interamente con modelli linguistici locali (LLM).


## Come usarlo

Segui questi passaggi per avviare il progetto sul tuo computer.

### 1. Scarica il Repository

Clona questo repository sulla tua macchina locale:

```bash
git clone https://github.com/bbnss/GloboNews.git
cd GloboNews
```

### 2. Configura il Backend

Il backend richiede Python e alcune dipendenze.

```bash
# Naviga nella cartella del backend
cd backend

# Installa le dipendenze
pip install -r requirements.txt

# Crea e configura le variabili d'ambiente
cp .env.example .env

# Modifica le fonti da cui scaricare le news
nano fonti.txt
```

Successivamente, apri il file `.env` con un editor di testo e inserisci le tue credenziali (API key, token, ecc.).

### 3. Avvia il Web Server

Per visualizzare il frontend, puoi usare un semplice server web Python dalla cartella `frontend`.

```bash
# Naviga nella cartella del frontend
cd ../frontend

# Avvia un server web locale
python3 -m http.server 8000
```

Apri il tuo browser e visita `http://localhost:8000` per vedere l'applicazione in funzione.

## Come funziona

Il sistema è suddiviso in due componenti principali:

*   **Backend**: Un insieme di script Python che si occupano di:
    *   Scaricare le ultime notizie da varie fonti italiane.
    *   Analizzare ogni articolo per estrarre parole chiave, geolocalizzare la notizia e generare un titolo accattivante.
    *   Selezionare l'icona più adatta a rappresentare il contenuto della notizia.
    *   Aggiornare un file `news_manifest.json` che verrà letto dal frontend.

*   **Frontend**: Un'interfaccia web semplice (HTML, CSS, JS) che:
    *   Legge i dati delle notizie dal file `news_manifest.json`.
    *   Visualizza le notizie su una mappa interattiva dell'Italia.
    *   Mostra le icone e i titoli, permettendo all'utente di esplorare le notizie geograficamente.

## 🤖 LLM Locale: Gemma 2

Questo progetto è stato sviluppato per funzionare **completamente con un LLM locale**. Tutta l'analisi del testo, l'estrazione di parole chiave e la generazione di contenuti sono gestite da **Gemma 3**, garantendo che nessun dato venga inviato a servizi cloud esterni.

## 🌐 Esempio Live

È disponibile una demo live del progetto. Trovi il link nella descrizione di questo repository.
