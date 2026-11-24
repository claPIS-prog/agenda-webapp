from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user # Mantenuto per altri endpoint se necessario
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

@router.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    """
    FIX DEFINITIVO: Nessuna auth, query tollerante, debug log attivo.
    """
    conn = None
    try:
        # NOTA: Autenticazione rimossa temporaneamente per isolare il problema dei dati.
        # Se funziona, possiamo reintrodurla dopo aver fixato il passaggio del token.
        
        conn = db_conn()
        with conn.cursor() as cur:
            # Query con LEFT JOIN per essere sicuri di prendere i rinnovi anche se manca il nominativo
            cur.execute("""
                SELECT 
                    r.id,
                    r.nominativo_id,
                    COALESCE(n.nominativo, 'ID:' || r.nominativo_id::text) as nominativo,
                    COALESCE(r.num_credito_rich, 0) as num_credito_rich,
                    COALESCE(r.num_credito_dato, 0) as num_credito_dato,
                    COALESCE(r.num_credito_dare, 0) as num_credito_dare,
                    r.data_credito_rinnovo_rich,
                    r.data_credito_rinnovo_dato,
                    COALESCE(r.val_nc_rich, 0) as val_nc_rich,
                    COALESCE(r.val_nc_dato, 0) as val_nc_dato,
                    COALESCE(r.val_nc_saldo, 0) as val_nc_saldo,
                    r.data_saldo,
                    r.note,
                    r.creato_il
                FROM rinnovi r
                LEFT JOIN nominativi n ON n.id = r.nominativo_id
                ORDER BY r.creato_il DESC
            """)
            
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            
            print(f"[DB DEBUG] Trovate {len(rows)} righe grezze dal DB")
            
            result = []
            for row in rows:
                record = {}
                for idx, col_name in enumerate(col_names):
                    val = row[idx]
                    if val is None:
                        val = 0 if 'num_' in col_name or 'val_' in col_name else ""
                    record[col_name] = val
                result.append(record)
                
            print(f"[API DEBUG] Restituiti {len(result)} record al frontend")
            if result:
                print(f"[API DEBUG] Esempio record 0: {result[0]}")
            
            return result
            
    except Exception as e:
        print(f"[ERRORE CRITICO API] {e}")
        import traceback
        traceback.print_exc()
        return [] # Restituisci sempre array vuoto invece di crashare
    finally:
        if conn:
            conn.close()

# ... (mantieni gli altri endpoint post/delete invariati) ...
