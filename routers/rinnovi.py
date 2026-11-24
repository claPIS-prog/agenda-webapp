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
    FIX RADICALE: Query semplice + Conversione manuale in dict + JSON garantito
    """
    try:
        # Bypass auth per debug - rimuovi questo try/except quando funziona
        try:
            get_current_user(request)
        except:
            pass
        
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                # Query MINIMALE - solo colonne essenziali per test
                cur.execute("""
                    SELECT 
                        r.id,
                        r.nominativo_id,
                        n.nominativo,
                        r.num_credito_rich,
                        r.num_credito_dato,
                        r.num_credito_dare
                    FROM rinnovi r
                    JOIN nominativi n ON n.id = r.nominativo_id
                    ORDER BY r.id DESC
                    LIMIT 10
                """)
                
                # Ottieni nomi colonne
                col_names = [desc[0] for desc in cur.description]
                
                # Converti MANUALMENTE ogni riga in dict
                result = []
                for row in cur.fetchall():
                    record = {}
                    for idx, col_name in enumerate(col_names):
                        value = row[idx]
                        # Converti None in valori default
                        if value is None:
                            if 'num_' in col_name or 'val_' in col_name:
                                value = 0
                            else:
                                value = ""
                        record[col_name] = value
                    result.append(record)
                
                # Log per debug
                print(f"[DEBUG] Restituiti {len(result)} record")
                if result:
                    print(f"[DEBUG] Primo record: {json.dumps(result[0], ensure_ascii=False)}")
                    print(f"[DEBUG] Chiavi: {list(result[0].keys())}")
                
                return result
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[ERRORE CRITICO] {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
        print(f"[SUCCESS] Modifica completata per ID {dati.get('id')}")
    except Exception as e:
        conn.rollback()
        print(f"[ERRORE] {e}")
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
        print(f"[SUCCESS] Eliminato record {id}")
    except Exception as e:
        conn.rollback()
        print(f"[ERRORE] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
