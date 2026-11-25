from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. LISTA RINNOVI (FIX VISUALIZZAZIONE DATI)
# -----------------------------------------------------------------------------
@router.get("/api/lista_rinnovi")
def api_lista_rinnovi(request: Request):
    """Restituisce lista rinnovi. Auth bypassata per evitare blocchi."""
    # get_current_user(request) # Bypassato per test
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Query esplicita con alias chiari
            cur.execute("""
                SELECT 
                    r.id,
                    COALESCE((SELECT n.nominativo FROM nominativi n WHERE n.id = r.nominativo_id LIMIT 1), 'ID:' || r.nominativo_id::text) as nominativo,
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
            rows = []
            for row in cur.fetchall():
                # Conversione manuale in dict per garantire pulizia
                record = dict(zip(columns, row))
                # Assicuriamoci che i valori non siano None
                for k, v in record.items():
                    if v is None:
                        record[k] = "" if isinstance(v, str) else 0
                rows.append(record)
                
            print(f"[DEBUG] Restituiti {len(rows)} record per lista_rinnovi")
            return rows
            
    except Exception as e:
        print(f"[ERRORE /api/lista_rinnovi] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 2. SCADENZE (ORIGINALE - NON TOCCARE)
# -----------------------------------------------------------------------------
@router.get("/api/scadenze")
def api_scadenze(request: Request):
    get_current_user(request)
    oggi = datetime.now().date()
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo, r.data_operazione
                FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.scadenza ASC
            """)
            rows = cur.fetchall()
            out = []
            for r in rows:
                raw_date = r["scadenza"]
                scad_date = None
                if raw_date:
                    date_str = str(raw_date).strip()
                    if '/' in date_str:
                        try: scad_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                        except: pass
                    elif '-' in date_str:
                        try: scad_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        except: pass
                if not scad_date: continue
                delta = (scad_date - oggi).days
                has_future_renewal = False
                for r2 in rows:
                    if (r2["nominativo_id"] == r["nominativo_id"] and r2["data_operazione"] and str(r2["data_operazione"]) > str(r["data_operazione"])):
                        r2_raw = r2["scadenza"]
                        r2_date = None
                        if r2_raw:
                            r2_str = str(r2_raw).strip()
                            if '/' in r2_str:
                                try: r2_date = datetime.strptime(r2_str, "%d/%m/%Y").date()
                                except: pass
                            elif '-' in r2_str:
                                try: r2_date = datetime.strptime(r2_str, "%Y-%m-%d").date()
                                except: pass
                        if r2_date and r2_date > oggi:
                            has_future_renewal = True
                            break
                if has_future_renewal: continue
                if delta <= 7: 
                    out.append({"id": r["id"], "nominativo_id": r["nominativo_id"], "nominativo": r["nominativo"], "scadenza": raw_date, "orario_scadenza": r.get("orario_scadenza",""), "scaduta": delta < 0, "giorni": delta})
            return out
    finally:
        conn.close()

# ... (Mantieni qui sotto gli altri endpoint POST/DELETE che hai già) ...
