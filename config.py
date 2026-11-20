import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTHORIZED_IDS = {int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x}

if not DATABASE_URL or not BOT_TOKEN:
    raise SystemExit("DATABASE_URL o BOT_TOKEN mancanti.")

ALL_MODULES = [
    "nominativo", "lista", "scadenze", "rinnovi", "storico_rinnovi",
    "saldo_rinnovi", "reseller", "procuratori", "server", "nota",
    "credenziali", "permessi", "dispositivi", "sistemi_op", "buffett",
    "pagamenti", "operatori_it", "tabelle", "crediti"
]

TABELLE_COLONNE = {
    'dispositivi': 'nome',
    'sistemi_operativi': 'nome',
    'buffett': 'nome',
    'metodi_pagamento': 'nome',
    'resellers': 'nominativo',
    'servers': 'nominativo',
    'procuratori': 'nominativo',
    'operatori_it': 'nome'
}