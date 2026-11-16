# server.py
import os
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("❌ DATABASE_URL mancante.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS nominativi (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, user_id TEXT, password TEXT, cellulare TEXT, whatsapp TEXT, server TEXT, reseller TEXT, procuratore TEXT, uso_vpn INTEGER DEFAULT 0, quale_vpn TEXT, residenza TEXT, applicazioni TEXT, dispositivi TEXT, pacchetto TEXT, fornitore TEXT, tipo_pagamento TEXT, prezzo REAL DEFAULT 0, cadenza TEXT, tipo_linea TEXT, data_iscrizione TEXT, creato_il TEXT);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS rinnovi (id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), tipo TEXT, data_operazione TEXT, mesi INTEGER, scadenza TEXT, importo_acconto REAL DEFAULT 0, importo_saldo REAL DEFAULT 0, data_acconto TEXT, data_saldo TEXT, note TEXT, creato_il TEXT);""")
            cur.execute("CREATE TABLE IF NOT EXISTS servers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS resellers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS procuratori (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
        conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.get("/api/contatti")
def api_contatti():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, user_id, prezzo, cadenza, tipo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/scadenze")
def api_scadenze():
    oggi = datetime.now()
    tra30 = oggi + timedelta(days=30)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.scadenza, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id")
            rows = cur.fetchall()
            scadenze_list = []
            for r in rows:
                try:
                    scad = datetime.strptime(r["scadenza"], "%d/%m/%Y")
                    if oggi <= scad <= tra30:
                        giorni = (scad - oggi).days
                        scadenze_list.append({"nominativo": r["nominativo"], "scadenza": r["scadenza"], "giorni": giorni})
                except:
                    continue
            scadenze_list.sort(key=lambda x: x["giorni"])
            return scadenze_list
    finally:
        conn.close()

@app.get("/api/nominativi")
def api_nominativi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

# --- API PER RESELLER, PROCURATORI, SERVER ---

@app.get("/api/resellers")
def api_resellers():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM resellers ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/procuratori")
def api_procuratori():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM procuratori ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/servers")
def api_servers():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM servers ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

class RinnovoPayload(BaseModel):
    dati: dict

@app.post("/api/rinnovo")
def api_rinnovo(payload: RinnovoPayload):
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                           (int(dati.get("nominativo_id")), dati.get("tipo", "rinnovo"), dati.get("data_operazione"), int(dati.get("mesi")), dati.get("scadenza"), float(dati.get("importo_acconto", 0)), float(dati.get("importo_saldo", 0)), "", "", "", datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

class AzionePayload(BaseModel):
    dati: dict

@app.post("/api/azione")
def api_azione(payload: AzionePayload):
    dati = payload.dati
    azione = dati.get("azione", "")
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if azione == "cancella":
                cur.execute("DELETE FROM nominativi WHERE id = %s", (dati.get("id"),))
            elif azione == "nuovo":
                cur.execute("""INSERT INTO nominativi (nominativo, user_id, password, cellulare, whatsapp, server, reseller, procuratore, prezzo, cadenza, tipo, data_iscrizione, creato_il) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                (dati.get("nominativo", ""), dati.get("user_id", ""), dati.get("password", ""), dati.get("cellulare", ""), dati.get("whatsapp", ""), dati.get("server", ""), dati.get("reseller", ""), dati.get("procuratore", ""), float(dati.get("prezzo", 0)), dati.get("cadenza", ""), dati.get("tipo", ""), datetime.now().strftime("%d/%m/%Y"), datetime.now().isoformat()))
            elif azione == "modifica":
                cur.execute("""UPDATE nominativi SET nominativo=%s, user_id=%s, password=%s, cellulare=%s, whatsapp=%s, server=%s, reseller=%s, procuratore=%s, prezzo=%s, cadenza=%s, tipo=%s WHERE id=%s""", 
                (dati.get("nominativo"), dati.get("user_id"), dati.get("password"), dati.get("cellulare"), dati.get("whatsapp"), dati.get("server"), dati.get("reseller"), dati.get("procuratore"), float(dati.get("prezzo", 0)), dati.get("cadenza"), dati.get("tipo"), dati.get("id")))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)