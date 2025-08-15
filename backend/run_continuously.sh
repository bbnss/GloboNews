#!/bin/bash

# Script per eseguire geoloc_fetcher.py in un ciclo continuo
# con una pausa di 5 minuti tra ogni esecuzione.

# Assicurati che lo script si fermi correttamente se viene interrotto (es. con Ctrl+C)
trap "echo; echo 'Script interrotto dall utente.'; exit" INT

# Ciclo infinito
while true; do
  echo "-----------------------------------------------------"
  echo "Avvio di geoloc_fetcher.py in corso... (Timestamp: $(date))"
  echo "-----------------------------------------------------"
  
  # Attiva l'ambiente virtuale ed esegui lo script Python
  source venv/bin/activate && python3 geoloc_fetcher.py
  
  echo "-----------------------------------------------------"
  echo "Esecuzione completata."
  echo "In attesa di 120 minuti prima della prossima esecuzione..."
  echo "Premi Ctrl+C per interrompere."
  echo "-----------------------------------------------------"
  
  # Pausa di 7200 secondi (120 minuti)
  sleep 7200
done
