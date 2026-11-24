from datetime import datetime
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class CreditoPayload(BaseModel):
    dati: dict

@router.post("/api/credito")
def api_credito(payload: CreditoPayload, request: Request):
    """PUNTO C: Salva un nuovo acquisto credito con contatore"""
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crediti (
                    fornitore, data_acquisto, quantita, valore_totale, 
                    valore_singolo, note, creato_il
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                dati.get("fornitore",""), 
                dati.get("data_acquiso",""),
                int(dati.get("quantita", 1)), # PUNTO C: Contatore
                float(dati.get("valore_totale", 0)),
                float(dati.get("valore_singolo", 0)),
                dati.get("note",""),
                datetime.now().isoformat()
            ))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    """PUNTO C: Restituisce crediti utilizzabili per i rinnovi"""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Unione tra saldo storico e nuovi acquisti non usati
            cur.execute("""
                SELECT id, 'Saldo Storico' as tipo, quantita, valore_singolo as valore, data_acquisto as data_ref 
                FROM crediti WHERE quantita > 0
                UNION ALL
                SELECT id, 'Nuovo Acquisto', quantita, valore_singolo, data_acquisto 
                FROM crediti ORDER BY data_ref DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()
