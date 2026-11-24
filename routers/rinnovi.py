from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

router = APIRouter()

# -----------------------------------------------------------------------------
# ENDPOINT SCADENZE (NON MODIFICATO - FUNZIONANTE)
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
                FROM rinnovi r 
                JOIN nominativi n ON n.id = r.nominativo_id 
                ORDER BY r.scadenza ASC
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
                
                # Escludi se esiste un rinnovo futuro attivo
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

# -----------------------------------------------------------------------------
# ENDPOINT STORICO RINNOVI (FIX 404)
# -----------------------------------------------------------------------------
@router.get("/api/rinnovi_lista")
def api_rinnovi_lista(request: Request):
    """Restituisce lo storico completo dei rinnovi"""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    r.id, 
                    r.nominativo_id, 
                    n.nominativo, 
                    r.tipo, 
                    r.data_operazione, 
                    r.mesi, 
                    r.scadenza, 
                    r.orario_scadenza, 
                    r.importo_acconto, 
                    r.importo_saldo, 
                    r.data_acconto, 
                    r.data_saldo, 
                    r.note, 
                    r.creato_il, 
                    r.num_credito_rich, 
                    r.num_credito_dato, 
                    r.num_credito_dare, 
                    r.data_credito_rinnovo_rich, 
                    r.data_credito_rinnovo_dato, 
                    r.val_singolo_nc_rich, 
                    r.val_nc_rich, 
                    r.credito_id
                FROM rinnovi r 
                JOIN nominativi n ON n.id = r.nominativo_id 
                ORDER BY r.creato_il DESC
            """)
            
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            return rows
            
    except Exception as e:
        print(f"[ERRORE /api/rinnovi_lista] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# ENDPOINT GESTIONE RINNOVI (POST / DELETE)
# -----------------------------------------------------------------------------
@router.post("/api/rinnovo")
def api_rinnovo(payload: RinnovoPayload, request: Request):
    get_current_user(request)
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
                        data_credito_rinnovo_rich=%s,
                        data_credito_rinnovo_dato=%s,
                        val_nc_rich=%s,
                        num_credito_dare=%s,
                        data_saldo=%s,
                        val_nc_dato=%s,
                        val_nc_saldo=%s,
                        note=%s
                    WHERE id=%s
                """, (
                    int(dati.get("num_credito_rich", 0)),
                    int(dati.get("num_credito_dato", 0)),
                    dati.get("data_credito_rinnovo_rich", ""),
                    dati.get("data_credito_rinnovo_dato", ""),
                    float(dati.get("val_nc_rich", 0)),
                    int(dati.get("num_credito_dare", 0)),
                    dati.get("data_saldo", ""),
                    float(dati.get("val_nc_dato", 0)),
                    float(dati.get("val_nc_saldo", 0)),
                    dati.get("note", ""),
                    int(dati.get("id"))
                ))
            
            elif azione in ["nuovo", "rinnovo"]:
                num_rich = int(dati.get("num_credito_rich", 0))
                num_dato = int(dati.get("num_credito_dato", 0))
                val_singolo = float(dati.get("val_singolo_nc_rich", 0))
                credito_id = dati.get("credito_id") or None
                
                cur.execute("""INSERT INTO rinnovi (
                    nominativo_id, tipo, data_operazione, mesi, scadenza, orario_scadenza, 
                    importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il, 
                    num_credito_rich, num_credito_dato, num_credito_dare, 
                    data_credito_rinnovo_rich, data_credito_rinnovo_dato, 
                    val_singolo_nc_rich, val_nc_rich, credito_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                (int(dati.get("nominativo_id")), dati.get("tipo","rinnovo"), dati.get("data_operazione"), 
                 int(dati.get("mesi",12)), dati.get("scadenza"), dati.get("orario_scadenza",""), 
                 float(dati.get("importo_acconto",0)), float(dati.get("importo_saldo",0)), 
                 datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_acconto",0))>0 else "", 
                 datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_saldo",0))>0 else "", 
                 dati.get("note",""), datetime.now().isoformat(), 
                 num_rich, num_dato, num_rich - num_dato, 
                 dati.get("data_credito_rinnovo_rich",""), dati.get("data_credito_rinnovo_dato",""), 
                 val_singolo, num_rich * val_singolo, credito_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/rinnovo/{id}")
def api_rinnovo_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saldo_rinnovi WHERE rinnovo_id = %s", (id,))
            cur.execute("DELETE FROM rinnovi WHERE id = %s", (id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
