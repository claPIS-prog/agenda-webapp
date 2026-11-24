from datetime import datetime
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from pydantic import BaseModel

router = APIRouter()

class CreditoPayload(BaseModel):
    dati: dict

@router.post("/api/credito")
def api_credito(payload: CreditoPayload, request: Request):
    """
    PUNTO C: Salva un nuovo acquisto credito.
    Il CONTATORE (ID) viene generato AUTOMATICAMENTE dal backend.
    """
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Genera contatore automatico: MAX(id) + 1
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM crediti")
            nuovo_id = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO crediti (
                    id, fornitore, data_acquisto, quantita, valore_totale, 
                    valore_singolo, note, creato_il
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                nuovo_id, # Contatore automatico
                dati.get("fornitore",""), 
                dati.get("data_acquisto",""),
                int(dati.get("quantita", 1)), 
                float(dati.get("valore_totale", 0)),
                float(dati.get("valore_singolo", 0)),
                dati.get("note",""),
                datetime.now().isoformat()
            ))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": nuovo_id}

@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    """Restituisce crediti utilizzabili per i rinnovi"""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
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
