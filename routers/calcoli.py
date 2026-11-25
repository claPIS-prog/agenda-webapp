from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from pydantic import BaseModel

router = APIRouter()

class CreditoPayload(BaseModel):
    dati: dict

# -----------------------------------------------------------------------------
# 1. ENDPOINT LISTA CALCOLI (FIX SINTASSI E INDENTAZIONE)
# -----------------------------------------------------------------------------
@router.get("/api/calcoli")
def api_calcoli(request: Request):
    """Restituisce dati dashboard calcoli dalla tabella 'calcoli'."""
    # get_current_user(request)  # Bypassato temporaneamente per test
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Legge dalla tabella 'calcoli' come nel tuo server.py originale
            cur.execute("SELECT * FROM calcoli ORDER BY creato_il DESC")
            rows = cur.fetchall()
            
            # Converti in lista di dict puliti
            result = []
            for row in rows:
                if isinstance(row, dict):
                    record = dict(row)
                else:
                    columns = [desc[0] for desc in cur.description]
                    record = dict(zip(columns, row))
                
                # Pulizia None
                for k, v in list(record.items()):
                    if v is None:
                        record[k] = "" if isinstance(v, str) or k in ['note', 'info_saldo_nuovo', 'info_saldo_rinnovo_nuovo', 'info_saldo_rinnovo'] else 0
                
                result.append(record)
            
            print(f"[DEBUG] Restituiti {len(result)} record da tabella calcoli")
            return result
            
    except Exception as e:
        print(f"[ERRORE /api/calcoli] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 2. SALDO INIZIALE (FIX INDENTAZIONE)
# -----------------------------------------------------------------------------
@router.post("/api/saldo_iniziale")
def api_saldo_iniziale(payload: CreditoPayload, request: Request):
    """Salva o aggiorna il SALDO INIZIALE con ID fisso = 1."""
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crediti WHERE id = 1 LIMIT 1")
            exists = cur.fetchone()
            
            qta = int(dati.get("quantita", 0))
            unitario = float(dati.get("valore_singolo", 0))
            totale = float(dati.get("valore_totale", 0))
            
            if exists:
                cur.execute("""
                    UPDATE crediti SET 
                        quantita=%s, valore_singolo=%s, valore_totale=%s,
                        data_acquisto=%s, note=%s, creato_il=%s 
                    WHERE id = 1
                """, (
                    qta, unitario, totale,
                    dati.get("data_acquisto", ""),
                    dati.get("note", "Saldo Iniziale"),
                    datetime.now().isoformat()
                ))
            else:
                cur.execute("""
                    INSERT INTO crediti (id, fornitore, data_acquisto, quantita, 
                        valore_singolo, valore_totale, note, creato_il)
                    VALUES (1, 'SALDO INIZIALE', %s, %s, %s, %s, 'Saldo Iniziale', %s)
                """, (
                    dati.get("data_acquisto", ""),
                    qta, unitario, totale,
                    datetime.now().isoformat()
                ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}

# -----------------------------------------------------------------------------
# 3. NUOVO CREDITO (FIX INDENTAZIONE)
# -----------------------------------------------------------------------------
@router.post("/api/credito")
def api_credito(payload: CreditoPayload, request: Request):
    """Salva un NUOVO ACQUISTO con ID automatico progressivo."""
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 1) + 1 FROM crediti")
            nuovo_id = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO crediti (id, fornitore, data_acquisto, quantita, 
                    valore_singolo, valore_totale, note, creato_il)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nuovo_id,
                dati.get("fornitore", ""),
                dati.get("data_acquisto", ""),
                int(dati.get("quantita", 1)),
                float(dati.get("valore_singolo", 0)),
                float(dati.get("valore_totale", 0)),
                dati.get("note", ""),
                datetime.now().isoformat()
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True, "id": nuovo_id}

# -----------------------------------------------------------------------------
# 4. CREDITI DISPONIBILI (FIX SPAZI URL E DOCSTRING)
# -----------------------------------------------------------------------------
@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    """Restituisce tutti i crediti con quantità > 0 per il menu Rinnovi."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, 
                CASE WHEN id = 1 THEN 'Saldo Iniziale' ELSE 'Acquisto #' || id END as tipo,
                quantita, valore_singolo as valore, data_acquisto as data_ref
                FROM crediti WHERE quantita > 0 ORDER BY id ASC
            """)
            return cur.fetchall()
    finally:
        conn.close()
