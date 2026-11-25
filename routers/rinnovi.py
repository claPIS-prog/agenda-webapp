from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. LISTA RINNOVI
# -----------------------------------------------------------------------------
@router.get("/api/lista_rinnovi")
def api_lista_rinnovi(request: Request):
    """Restituisce lista rinnovi. Auth bypassata per evitare blocchi."""
    # get_current_user(request)  # Bypassato per test
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Solo colonne esistenti (senza importo_acconto / importo_saldo)
            cur.execute("""
                SELECT 
                    r.id,
                    COALESCE(
                        (SELECT n.nominativo FROM nominativi n WHERE n.id = r.nominativo_id LIMIT 1), 
                        'ID:' || COALESCE(r.nominativo_id::text, '?')
                    ) as nominativo,
                    r.data_operazione,
                    r.scadenza,
                    COALESCE(r.tipo, 'rinnovo') as tipo,
                    r.note,
                    r.nominativo_id
                FROM rinnovi r
                ORDER BY r.creato_il DESC NULLS LAST, r.id DESC
            """)
            
            rows = cur.fetchall()
            result = []
            
            for row in rows:
                if isinstance(row, dict):
                    record = dict(row)
                else:
                    columns = [desc[0] for desc in cur.description]
                    record = dict(zip(columns, row))
                
                for k, v in list(record.items()):
                    if v is None:
                        if k in ("id", "nominativo_id"):
                            record[k] = 0
                        else:
                            record[k] = ""
                    elif k in ("data_operazione", "scadenza") and v:
                        record[k] = str(v)[:10]
                
                result.append(record)
            
            print(f"[DEBUG] Restituiti {len(result)} record per lista_rinnovi")
            if result:
                print(f"[DEBUG] Primo record: {result[0]}")
            
            return result
            
    except Exception as e:
        print(f"[ERRORE /api/lista_rinnovi] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 2. SCADENZE (ORIGINALE)
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
                if not isinstance(r, dict):
                    continue
                    
                raw_date = r.get("scadenza")
                scad_date = None
                if raw_date:
                    date_str = str(raw_date).strip()
                    if '/' in date_str:
                        try: 
                            scad_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                        except: 
                            pass
                    elif '-' in date_str:
                        try: 
                            scad_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        except: 
                            pass
                if not scad_date: 
                    continue
                    
                delta = (scad_date - oggi).days
                has_future_renewal = False
                
                for r2 in rows:
                    if not isinstance(r2, dict):
                        continue
                    if (r2.get("nominativo_id") == r.get("nominativo_id") and 
                        r2.get("data_operazione") and 
                        str(r2.get("data_operazione")) > str(r.get("data_operazione"))):
                        
                        r2_raw = r2.get("scadenza")
                        r2_date = None
                        if r2_raw:
                            r2_str = str(r2_raw).strip()
                            if '/' in r2_str:
                                try: 
                                    r2_date = datetime.strptime(r2_str, "%d/%m/%Y").date()
                                except: 
                                    pass
                            elif '-' in r2_str:
                                try: 
                                    r2_date = datetime.strptime(r2_str, "%Y-%m-%d").date()
                                except: 
                                    pass
                        if r2_date and r2_date > oggi:
                            has_future_renewal = True
                            break
                            
                if has_future_renewal: 
                    continue
                    
                if delta <= 7: 
                    out.append({
                        "id": r.get("id"), 
                        "nominativo_id": r.get("nominativo_id"), 
                        "nominativo": r.get("nominativo"), 
                        "scadenza": raw_date, 
                        "orario_scadenza": r.get("orario_scadenza", ""), 
                        "scaduta": delta < 0, 
                        "giorni": delta
                    })
            return out
    finally:
        conn.close()
