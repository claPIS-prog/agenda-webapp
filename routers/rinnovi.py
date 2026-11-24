from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload
import json

# FIX CRITICO: Definizione esplicita del router
router = APIRouter()

@router.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    """
    FIX BACKEND: Query sicura con COALESCE per gestire NULL e garantire tipi numerici.
    Restituisce JSON pulito per il frontend.
    """
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Query esplicita con COALESCE per evitare errori se le colonne sono NULL
            # Se una colonna non esiste nel DB, PostgreSQL solleverà un errore chiaro qui
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
            
            # Converti in lista di dizionari JSON-safe
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            return rows
            
    except Exception as e:
        # Logga l'errore reale nel server per debug
        print(f"ERRORE CRITICO DB in api_elenco_rinnovi: {e}")
        raise HTTPException(status_code=500, detail=f"Errore Database: {str(e)}")
    finally:
        conn.close()

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
