import os
import sys

# Lista dei file da modificare
FILES = [
    "index.html",
    "elencazione.html",
    "scadenze.html",
    "rinnovi.html",
    "rinnovi_lista.html",
    "saldo_rinnovi.html",
    "note.html",
    "credenziali.html",
    "permessi.html",
    "notifiche.html",
    "operatori_it.html",
    "dispositivi.html",
    "sistemi_operativi.html",
    "buffett.html",
    "metodi_pagamento.html",
    "reseller.html",
    "procuratori.html",
    "server.html"
]

TARGET_LINE = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
INSERT_LINE = '<script src="/auth.js"></script>'

def fix_file(filename):
    """Modifica un singolo file HTML aggiungendo auth.js"""
    if not os.path.exists(filename):
        return False, "File non trovato"
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if INSERT_LINE in content:
        return False, "Già modificato (auth.js già presente)"
    
    if TARGET_LINE not in content:
        return False, "Riga target non trovata"
    
    # Aggiungi la riga auth.js subito dopo la riga di Telegram WebApp
    new_content = content.replace(TARGET_LINE, TARGET_LINE + '\n' + INSERT_LINE)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True, "Modificato con successo"

def main():
    print("=" * 50)
    print("   FIX AUTOMATICO: Aggiunta auth.js a tutti i file HTML")
    print("=" * 50)
    print()
    
    # Verifica che auth.js esista
    if not os.path.exists("auth.js"):
        print("⚠️  ATTENZIONE: Il file 'auth.js' non esiste nella cartella!")
        print("   Crealo prima su GitHub, poi esegui di nuovo questo script.")
        print()
        risposta = input("Vuoi continuare comunque? (s/n): ").strip().lower()
        if risposta != 's':
            print("Operazione annullata.")
            return
    
    success = 0
    failed = 0
    risultati = []
    
    for f in FILES:
        ok, msg = fix_file(f)
        status = "✅" if ok else "❌"
        risultati.append((status, f, msg))
        if ok:
            success += 1
        else:
            failed += 1
    
    # Stampa risultati
    print("Risultati:")
    print("-" * 50)
    for status, f, msg in risultati:
        print(f"{status} {f:30s} {msg}")
    
    print()
    print("=" * 50)
    print(f"RIEPILOGO:")
    print(f"  ✅ Modificati: {success}")
    print(f"  ❌ Saltati/Errore: {failed}")
    print(f"  📁 Totale file: {len(FILES)}")
    print("=" * 50)
    
    if success > 0:
        print()
        print("🎉 Operazione completata!")
        print("Ora carica i file modificati su GitHub e attendi il deploy.")
    else:
        print()
        print("⚠️  Nessun file è stato modificato. Controlla i messaggi di errore.")

if __name__ == "__main__":
    main()