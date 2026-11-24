from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

@router.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    """
    FIX CRITICO: Conversione esplicita righe DB -> Dict Python -> JSON Pulito.
    Elimina qualsiasi ambiguità sul formato dei dati restituiti.
    """
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    r.id, 
                    r.nominativo_id, 
                    n.nominativo, 
                    COALESCE(r.num_credito_rich, 0) as num_credito_rich, 
                    COALESCE(r.num_credito_dato, 0) as num_credito_dato, 
                    COALESCE(r.num_credito_dare, 0) as num_credito_dare, 
                    r.data_credito_rinnovo_rich, 
                    r.data_credito_rinnovo_dato, 
                    COALESCE(r.val_nc_rich, 0) as val_nc_rich,
                    COALESCE(r.val_nc_dato, 0) as val_nc_dato,
                    COALESCE(r.val_nc_saldo, 0) as val_nc_saldo,
                    r.data_saldo,
                    r.note
                FROM rinnovi r 
                INNER JOIN nominativi n ON n.id = r.nominativo_id 
                ORDER BY r.creato_il DESC
            """)
            
            # FIX: Otteniamo i nomi delle colonne dalla descrizione del cursore
            col_names = [desc[0] for desc in cur.description]
            
            # FIX: Convertiamo ogni riga (tupla) in un dizionario {colonna: valore}
            rows = []
            for row in cur.fetchall():
                row_dict = dict(zip(col_names, row))
                rows.append(row_dict)
            
            # Debug log per verificare cosa stiamo inviando
            print(f"[DEBUG] Inviati {len(rows)} record. Primo record keys: {list(rows[0].keys()) if rows else 'NESSUNO'}")
            
            return rows
            
    except Exception as e:
        print(f"ERRORE DB: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# ... (mantieni gli altri endpoint post/delete invariati) ...
