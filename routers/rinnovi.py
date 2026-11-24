from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

# -----------------------------------------------------------------------------
# ENDPOINT LISTA RINNOVI (NUOVO - LAYOUT SEMPLICE COME LISTA CONTATTI)
# -----------------------------------------------------------------------------
@router.get("/api/lista_rinnovi")
def api_lista_rinnovi(request: Request):
    """Restituisce lista rinnovi semplice per il nuovo modulo 'Lista Rinnovi'"""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Query sicura: usa subquery per nominativo invece di JOIN diretta
            cur.execute("""
                SELECT 
                    r.id,
                    COALESCE(
                        (SELECT n.nominativo FROM nominativi n WHERE n.id = r.nominativo_id LIMIT 1),
                        'ID:' || r.nominativo_id::text
                    ) as nominativo,
                    r.data_operazione,
                    r.scadenza,
                    r.tipo,
                    r.importo_acconto,
                    r.importo_saldo,
                    r.note
                FROM rinnovi r
                ORDER BY r.creato_il DESC
            """)
            
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            return rows
            
    except Exception as e:
        print(f"[ERRORE /api/lista_rinnovi] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# ALTRI ENDPOINT (Scadenze, Gestione Rinnovi, ecc.) RIMANGONO INVARIATI
# -----------------------------------------------------------------------------
# ... (mantieni qui tutto il resto del codice precedente per scadenze, post, delete) ...
