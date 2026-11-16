# server.py
import os
import json
import time
from datetime import datetime
from urllib.parse import parse_qsl
import hmac
import hashlib

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
AUTHORIZED_IDS = {int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x}

if not DATABASE_URL:
    raise SystemExit("❌ DATABASE_URL mancante.")

app = FastAPI()

# CORS permissivo per sicurezza
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Inizializzazione Tabelle
# ------------------------------------------------------------
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nominativi (
                    id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, user_id TEXT, password TEXT, cellulare TEXT, whatsapp TEXT, server TEXT, reseller TEXT, procuratore TEXT, uso_vpn INTEGER DEFAULT 0, quale_vpn TEXT, residenza TEXT, applicazioni TEXT, dispositivi TEXT, pacchetto TEXT, fornitore TEXT, tipo_pagamento TEXT, prezzo REAL DEFAULT 0, cadenza TEXT, tipo_linea TEXT, data_iscrizione TEXT, creato_il TEXT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rinnovi (
                    id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), tipo TEXT, data_operazione TEXT, mesi INTEGER, scadenza TEXT, importo_acconto REAL DEFAULT 0, importo_saldo REAL DEFAULT 0, data_acconto TEXT, data_saldo TEXT, note TEXT, creato_il TEXT
                );
            """)
            cur.execute("CREATE TABLE IF NOT EXISTS servers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS resellers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS procuratori (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
        conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# BYPASS SICUREZZA (temporaneo)
def get_current_user(request: Request):
    return {"id": 129937740, "first_name": "Claudio"}

@app.get("/api/contatti")
def api_contatti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, user_id, prezzo, cadenza FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

class AzionePayload(BaseModel):
    dati: dict

@app.post("/api/azione")
def api_azione(payload: AzionePayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    azione = dati.get("azione", "")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if azione == "cancella":
                cur.execute("DELETE FROM nominativi WHERE id = %s", (dati.get("id"),))
            elif azione == "nuovo":
                cur.execute(
                    """INSERT INTO nominativi (nominativo, user_id, password, cellulare, whatsapp, server, reseller, procuratore, prezzo, cadenza, data_iscrizione, creato_il)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (dati.get("nominativo", ""), dati.get("user_id", ""), dati.get("password", ""), dati.get("cellulare", ""), dati.get("whatsapp", ""), dati.get("server", ""), dati.get("reseller", ""), dati.get("procuratore", ""), float(dati.get("prezzo", 0)), dati.get("cadenza", ""), datetime.now().strftime("%d/%m/%Y"), datetime.now().isoformat()))
            elif azione == "modifica":
                cur.execute(
                    """UPDATE nominativi SET nominativo=%s, user_id=%s, password=%s, cellulare=%s, whatsapp=%s, server=%s, reseller=%s, procuratore=%s, prezzo=%s, cadenza=%s WHERE id=%s""",
                    (dati.get("nominativo"), dati.get("user_id"), dati.get("password"), dati.get("cellulare"), dati.get("whatsapp"), dati.get("server"), dati.get("reseller"), dati.get("procuratore"), float(dati.get("prezzo", 0)), dati.get("cadenza"), dati.get("id")))
            else:
                raise HTTPException(400, f"Azione non gestita: {azione}")
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/health")
def health():
    return {"ok": True}

# --- SERVE I FILE STATICI (HTML) ---
# Questo permette a Render di servire elencazione.html
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)