from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from pydantic import BaseModel

router = APIRouter()

class CreditoPayload(BaseModel):
    dati: dict

@router.post("/api/saldo_iniziale")
def api_saldo_iniziale(payload: CreditoPayload, request: Request):
    get_current_user(request)
    dati = payload.dati or {}
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crediti WHERE id = 1 LIMIT 1")
            exists = cur.fetchone()
            
            qta = int(dati.get("quantita") or 0)
            unitario = float(dati.get("valore_singolo") or 0)
            totale = float(dati.get("valore_totale") or 0)
            
            if exists:
                cur.execute("""
                    UPDATE crediti SET 
                        quantita=%s, 
                        valore_singolo=%s,
                        valore_totale=%s,
                        data_acquisto=%s, 
                        note=%s, 
                        creato_il=%s 
                    WHERE id = 1
                """, (
                    qta,
                    unitario,
                    totale,
                    dati.get("data_acquisto", ""),
                    dati.get("note", "Saldo Iniziale"),
                    datetime.now().isoformat()
                ))
            else:
                cur.execute("""
                    INSERT INTO crediti (
                        id, fornitore, data_acquisto, quantita, 
                        valore_singolo, valore_totale, note, creato_il
                    ) VALUES (
                        1, 'SALDO INIZIALE', %s, %s, %s, %s, 'Saldo Iniziale', %s
                    )
                """, (
                    dati.get("data_acquisto", ""),
                    qta,
                    unitario,
                    totale,
                    datetime.now().isoformat()
                ))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/api/credito")
def api_credito(payload: CreditoPayload, request: Request):
    """
    Salva un NUOVO ACQUISTO.
    Gestione robusta dell'ID (funziona sia con tuple che con dict/RealDict).
    """
    get_current_user(request)
    dati = payload.dati or {}
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Genera ID in modo sicuro (funziona con qualsiasi tipo di cursore)
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM crediti")
            row = cur.fetchone()

            nuovo_id = 2
            if row is not None:
                if isinstance(row, dict):
                    # RealDictCursor o dict
                    nuovo_id = int(row.get("next_id") or row.get("id") or 2)
                elif isinstance(row, (list, tuple)):
                    nuovo_id = int(row[0] or 2)
                else:
                    # Altri tipi
                    try:
                        nuovo_id = int(row)
                    except:
                        nuovo_id = 2

            if nuovo_id < 2:
                nuovo_id = 2

            # Nota con modalità di pagamento
            note_finale = (dati.get("note") or "").strip()
            pagamento = (dati.get("modalita_pagamento") or "").strip()
            if pagamento:
                note_finale = f"[Pagamento: {pagamento}] {note_finale}".strip()

            cur.execute("""
                INSERT INTO crediti (
                    id, fornitore, data_acquisto, quantita, 
                    valore_totale, valore_singolo, note, creato_il
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nuovo_id,
                str(dati.get("fornitore") or ""),
                str(dati.get("data_acquisto") or ""),
                int(dati.get("quantita") or 1),
                float(dati.get("valore_totale") or 0),
                float(dati.get("valore_singolo") or 0),
                note_finale,
                datetime.now().isoformat()
            ))

        conn.commit()
        return {"ok": True, "id": nuovo_id}

    except Exception as e:
        conn.rollback()
        print(f"[ERRORE /api/credito] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, 
                    CASE 
                        WHEN id = 1 THEN 'Saldo Iniziale' 
                        ELSE 'Acquisto #' || id 
                    END as tipo, 
                    quantita, 
                    valore_singolo as valore, 
                    data_acquisto as data_ref 
                FROM crediti 
                WHERE quantita > 0 
                ORDER BY id ASC
            """)
            return cur.fetchall()
    finally:
        conn.close()
