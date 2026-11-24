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
    FIX DEFINITIVO: Query diretta su rinnovi SENZA JOIN.
    Gestisce il nominativo in modo sicuro fallback su ID.
    """
    conn = None
    try:
        conn = db_conn()
        with conn.cursor() as cur:
            # Query DIRETTA su rinnovi. Nessuna JOIN che possa fallire.
            # Usiamo COALESCE per gestire i NULL direttamente nel DB
            cur.execute("""
                SELECT 
                    r.id,
                    r.nominativo_id,
                    -- Fallback sicuro: se non abbiamo il nome, usiamo l'ID
                    COALESCE(
                        (SELECT n.nominativo FROM nominativi n WHERE n.id = r.nominativo_id LIMIT 1),
                        'ID:' || r.nominativo_id::text
                    ) as nominativo,
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
                ORDER BY r.creato_il DESC
            """)
            
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            
            print(f"[DB SUCCESS] Trovate {len(rows)} righe grezze")
            
            result = []
            for row in rows:
                record = {}
                for idx, col_name in enumerate(col_names):
                    val = row[idx]
                    # Gestione NULL robusta
                    if val is None:
                        if 'num_' in col_name or 'val_' in col_name:
                            val = 0
                        else:
                            val = ""
                    record[col_name] = val
                result.append(record)
                
            print(f"[API SUCCESS] Restituiti {len(result)} record al frontend")
            if result:
                print(f"[API DEBUG] Primo record: ID={result[0]['id']}, Nom={result[0]['nominativo']}")
            
            return result
            
    except Exception as e:
        print(f"[ERRORE CRITICO API] {e}")
        import traceback
        traceback.print_exc()
        return [] # Fallback sicuro
    finally:
        if conn:
            conn.close()

# ... (mantieni gli altri endpoint post/delete invariati) ...
