from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload

router = APIRouter()

@router.get("/api/scadenze")
def api_scadenze(request: Request):
    """
    FIX DEFINITIVO ERRORE 500: 
    Nessun cast ::date nella query SQL. Parsing sicuro in Python.
    """
    get_current_user(request)
    oggi = datetime.now().date()
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Query SENZA CAST ::date. Prendiamo tutte le scadenze potenziali
            cur.execute("""
                SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo, r.data_operazione
                FROM rinnovi r 
                JOIN nominativi n ON n.id = r.nominativo_id 
                ORDER BY r.scadenza ASC
            """)
            
            rows = cur.fetchall()
            out = []
            
            for r in rows:
                raw_date = r["scadenza"]
                scad_date = None
                
                # PARSING SICURO IN PYTHON (Gestisce DD/MM/YYYY e YYYY-MM-DD)
                if raw_date:
                    date_str = str(raw_date).strip()
                    if '/' in date_str:
                        try:
                            scad_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                        except ValueError: pass
                    elif '-' in date_str:
                        try:
                            scad_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        except ValueError: pass
                
                # Se la data non è valida, salta questo record
                if not scad_date: continue
                
                delta = (scad_date - oggi).days
                
                # Escludi se esiste un rinnovo futuro attivo per lo stesso nominativo
                has_future_renewal = False
                for r2 in rows:
                    if (r2["nominativo_id"] == r["nominativo_id"] and 
                        r2["data_operazione"] and r["data_operazione"] and
                        str(r2["data_operazione"]) > str(r["data_operazione"])):
                        
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
                
                # Mostra solo scadute o entro 7 giorni
                if delta <= 7: 
                    out.append({
                        "id": r["id"], 
                        "nominativo_id": r["nominativo_id"], 
                        "nominativo": r["nominativo"], 
                        "scadenza": raw_date, 
                        "orario_scadenza": r.get("orario_scadenza",""), 
                        "scaduta": delta < 0, 
                        "giorni": delta
                    })
                    
            return out
    finally:
        conn.close()

# ... resto del file invariato (crediti_disponibili, elenco_rinnovi, api_rinnovo, ecc.) ...
