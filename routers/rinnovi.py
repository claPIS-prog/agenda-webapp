
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
    FIX DEFINITIVO: Query sicura + Conversione esplicita in JSON pulito + Debug log
    """
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Prima verifichiamo quali colonne esistono realmente nella tabella
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rinnovi' 
                ORDER BY ordinal_position
            """)
            existing_cols = [row[0] for row in cur.fetchall()]
            print(f"[DEBUG] Colonne esistenti in rinnovi: {existing_cols}")
            
            # Costruiamo la query solo con le colonne che esistono
            select_parts = ["r.id", "r.nominativo_id", "n.nominativo"]
            
            # Mappatura sicura: se la colonna esiste, la includiamo con COALESCE
            col_mapping = {
                'num_credito_rich': 'COALESCE(r.num_credito_rich, 0) as num_credito_rich',
                'num_credito_dato': 'COALESCE(r.num_credito_dato, 0) as num_credito_dato',
                'num_credito_dare': 'COALESCE(r.num_credito_dare, 0) as num_credito_dare',
                'data_credito_rinnovo_rich': 'r.data_credito_rinnovo_rich',
                'data_credito_rinnovo_dato': 'r.data_credito_rinnovo_dato',
                'val_nc_rich': 'COALESCE(r.val_nc_rich, 0) as val_nc_rich',
                'val_nc_dato': 'COALESCE(r.val_nc_dato, 0) as val_nc_dato',
                'val_nc_saldo': 'COALESCE(r.val_nc_saldo, 0) as val_nc_saldo',
                'data_saldo': 'r.data_saldo',
                'note': 'r.note',
                'creato_il': 'r.creato_il'
            }
            
            for col_name, sql_expr in col_mapping.items():
                if col_name in existing_cols:
                    select_parts.append(sql_expr)
                else:
                    print(f"[WARNING] Colonna '{col_name}' non esiste, skipped")
            
            query = f"""
                SELECT {', '.join(select_parts)}
                FROM rinnovi r 
                INNER JOIN nominativi n ON n.id = r.nominativo_id 
                ORDER BY r.creato_il DESC
            """
            
            print(f"[DEBUG] Query eseguita: {query[:200]}...")
            cur.execute(query)
            
            # Converti in lista di dizionari
            columns = [desc[0] for desc in cur.description]
            rows = []
            for row in cur.fetchall():
                row_dict = dict(zip(columns, row))
                rows.append(row_dict)
            
            print(f"[DEBUG] Restituiti {len(rows)} record. Primo record: {rows[0] if rows else 'NESSUNO'}")
            
            return rows
            
    except Exception as e:
        print(f"[ERRORE CRITICO] {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
                # Verifica quali colonne esistono prima di aggiornare
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'rinnovi'
                """)
                existing = [row[0] for row in cur.fetchall()]
                
                update_parts = []
                values = []
                
                fields_to_update = [
                    ('num_credito_rich', int),
                    ('num_credito_dato', int),
                    ('data_credito_rinnovo_rich', str),
                    ('data_credito_rinnovo_dato', str),
                    ('val_nc_rich', float),
                    ('num_credito_dare', int),
                    ('data_saldo', str),
                    ('val_nc_dato', float),
                    ('val_nc_saldo', float),
                    ('note', str)
                ]
                
                for field_name, field_type in fields_to_update:
                    if field_name in existing:
                        update_parts.append(f"{field_name}=%s")
                        val = dati.get(field_name, 0 if field_type in [int, float] else "")
                        values.append(field_type(val) if val not in [None, ""] else (0 if field_type in [int, float] else ""))
                
                if update_parts:
                    values.append(int(dati.get("id")))
                    query = f"UPDATE rinnovi SET {', '.join(update_parts)} WHERE id=%s"
                    print(f"[DEBUG UPDATE] {query}")
                    cur.execute(query, values)
            
            elif azione in ["nuovo", "rinnovo"]:
                # Inserimento nuovo rinnovo (mantieni la tua logica esistente)
                pass
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERRORE UPDATE] {e}")
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
            # Verifica se esiste la tabella saldo_rinnovi prima di cancellare
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'saldo_rinnovi'
                )
            """)
            has_saldo_table = cur.fetchone()[0]
            
            if has_saldo_table:
                cur.execute("DELETE FROM saldo_rinnovi WHERE rinnovo_id = %s", (id,))
            
            cur.execute("DELETE FROM rinnovi WHERE id = %s", (id,))
        conn.commit()
        print(f"[DEBUG DELETE] Record {id} eliminato")
    except Exception as e:
        conn.rollback()
        print(f"[ERRORE DELETE] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
