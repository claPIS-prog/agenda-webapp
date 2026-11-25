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
    """
    Salva o aggiorna il SALDO INIZIALE con ID fisso = 1.
    Se non esiste, lo crea. Se esiste, lo aggiorna.
    """
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Verifica se esiste già un record con ID=1
            cur.execute("SELECT id FROM crediti WHERE id = 1 LIMIT 1")
            exists = cur.fetchone()
            
            if exists:
                # Aggiorna il saldo esistente
                cur.execute("""
                    UPDATE crediti SET 
                        quantita=%s, 
                        valore_totale=%s, 
                        valore_singolo=%s, 
                        data_acquisto=%s, 
                        note=%s, 
                        creato_il=%s 
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
                # Crea nuovo record con ID=1
                cur.execute("""
                    INSERT INTO crediti (
                        id, fornitore, data_acquisto, quantita, 
                        valore_totale, valore_singolo, note, creato_il
                    ) VALUES (
                        1, 'SALDO INIZIALE', %s, %s, %s, %s, 'Saldo Iniziale', %s
                    )
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
    """
    Salva un NUOVO ACQUISTO.
    Versione ultra-robusta contro errori 500.
    """
    get_current_user(request)
    dati = payload.dati or {}
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Genera ID in modo sicuro
            try:
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM crediti")
                row = cur.fetchone()
                if isinstance(row, dict):
                    nuovo_id = int(row.get("next_id") or 2)
                elif isinstance(row, (list, tuple)) and len(row) > 0:
                    nuovo_id = int(row[0] or 2)
                else:
                    nuovo_id = 2
            except Exception as e:
                print(f"[WARN] Errore lettura MAX(id): {e}")
                nuovo_id = 2

            if nuovo_id < 2:
                nuovo_id = 2

            # Nota con modalità di pagamento
            note_finale = (dati.get("note") or "").strip()
            pagamento = (dati.get("modalita_pagamento") or "").strip()
            if pagamento:
                note_finale = f"[Pagamento: {pagamento}] {note_finale}".strip()

            # Inserimento
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
        err_msg = str(e)
        print(f"[ERRORE /api/credito] {err_msg}")
        raise HTTPException(status_code=500, detail=err_msg)
    finally:
        conn.close()

@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    """
    Restituisce tutti i crediti con quantità > 0 per il menu Rinnovi.
    Etichetta ID=1 come 'Saldo Iniziale', gli altri come 'Acquisto #X'.
    """
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
