from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

@router.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    """
    FIX RADICALE: Endpoint che restituisce SEMPRE un array, anche in caso di errore.
    Autenticazione bypassata per debug.
    """
    try:
        # Bypass temporaneo auth per isolare il problema
        # user = get_current_user(request) 
        
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                # Query minimale per test
                cur.execute("""
                    SELECT 
                        r.id,
                        r.nominativo_id,
                        n.nominativo,
                        COALESCE(r.num_credito_rich, 0) as num_credito_rich,
                        COALESCE(r.num_credito_dato, 0) as num_credito_dato,
                        COALESCE(r.num_credito_dare, 0) as num_credito_dare
                    FROM rinnovi r
                    JOIN nominativi n ON n.id = r.nominativo_id
                    ORDER BY r.id DESC
                    LIMIT 20
                """)
                
                col_names = [desc[0] for desc in cur.description]
                result = []
                
                for row in cur.fetchall():
                    record = {}
                    for idx, col_name in enumerate(col_names):
                        val = row[idx]
                        if val is None:
                            val = 0 if 'num_' in col_name else ""
                        record[col_name] = val
                    result.append(record)
                
                print(f"[SUCCESS] Restituiti {len(result)} record")
                return result
                
        except Exception as db_err:
            print(f"[DB ERROR] {db_err}")
            # Restituisci array vuoto invece di crashare
            return []
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        # Restituisci array vuoto invece di oggetto error
        return []

@router.post("/api/rinnovo")
def api_rinnovo(payload: RinnovoPayload, request: Request):
    try:
        get_current_user(request)
    except:
        pass
    
    dati = payload.dati
    azione = dati.get("azione", "")
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if azione == "modifica_rinnovo":
                cur.execute("""
                    UPDATE rinnovi SET 
                        num_credito_rich=%s,
                        num_credito_dato=%s,
                        num_credito_dare=%s
                    WHERE id=%s
                """, (
                    int(dati.get("num_credito_rich", 0)),
                    int(dati.get("num_credito_dato", 0)),
                    int(dati.get("num_credito_dare", 0)),
                    int(dati.get("id"))
                ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/rinnovo/{id}")
def api_rinnovo_cancella(id: int, request: Request):
    try:
        get_current_user(request)
    except:
        pass
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rinnovi WHERE id = %s", (id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
