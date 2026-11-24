from datetime import datetime
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from pydantic import BaseModel

router = APIRouter()

class CreditoPayload(BaseModel):
    dati: dict

@router.post("/api/saldo_iniziale")
def api_saldo_iniziale(payload: CreditoPayload, request: Request):
    """Salva/Aggiorna il SALDO INIZIALE con ID fisso = 1"""
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crediti WHERE id = 1 LIMIT 1")
            exists = cur.fetchone()
            
            if exists:
                cur.execute("""
                    UPDATE crediti SET 
                        quantita=%s, valore_totale=%s, valore_singolo=%s, 
                        data_acquisto=%s, note=%s, creato_il=%s 
                    WHERE id = 1
                """, (
                    int(dati.get("quantita", 0)),
                    float(dati.get("valore_totale", 0)),
                    float(dati.get("valore_singolo", 0)),
                    dati.get("data_acquisto", ""),
                    dati.get("note", "Saldo Iniziale"),
                    datetime.now().isoformat()
                ))
            else:
                cur.execute("""
                    INSERT INTO crediti (id, fornitore, data_acquisto, quantita, valore_totale, valore_singolo, note, creato_il)
                    VALUES (1, 'SALDO INIZIALE', %s, %s, %s, %s, 'Saldo Iniziale', %s)
                """, (
                    dati.get("data_acquisto", ""),
                    int(dati.get("quantita", 0)),
                    float(dati.get("valore_totale", 0)),
                    float(dati.get("valore_singolo", 0)),
                    datetime.now().isoformat()
                ))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.post("/api/credito")
def api_credito(payload: CreditoPayload, request: Request):
    """Salva NUOVO ACQUISTO con ID automatico progressivo"""
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 1) + 1 FROM crediti")
            nuovo_id = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO crediti (id, fornitore, data_acquisto, quantita, valore_totale, valore_singolo, note, creato_il)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nuovo_id,
                dati.get("fornitore", ""),
                dati.get("data_acquisto", ""),
                int(dati.get("quantita", 1)),
                float(dati.get("valore_totale", 0)),
                float(dati.get("valore_singolo", 0)),
                dati.get("note", ""),
                datetime.now().isoformat()
            ))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": nuovo_id}

@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    """Restituisce crediti disponibili per Rinnovi"""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, 
                       CASE WHEN id = 1 THEN 'Saldo Iniziale' ELSE 'Acquisto #' || id END as tipo, 
                       quantita, valore_singolo as valore, data_acquisto as data_ref 
                FROM crediti 
                WHERE quantita > 0 
                ORDER BY id ASC
            """)
            return cur.fetchall()
    finally:
        conn.close()
