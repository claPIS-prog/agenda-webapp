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
    FIX DEFINITIVO: Query dinamica basata sulle colonne REALI esistenti nel DB.
    """
    conn = None
    try:
        conn = db_conn()
        with conn.cursor() as cur:
            # 1. Ottieni TUTTE le colonne reali della tabella rinnovi
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rinnovi'
            """)
            existing_cols = [row[0] for row in cur.fetchall()]
            print(f"[DEBUG] Colonne esistenti in 'rinnovi': {existing_cols}")
            
            # 2. Costruisci la query SOLO con le colonne che esistono
            select_parts = ["r.id", "r.nominativo_id"]
            
            # Mappatura sicura: se la colonna esiste, includila
            col_map = {
                'nominativo': "(SELECT n.nominativo FROM nominativi n WHERE n.id = r.nominativo_id LIMIT 1)",
                'num_credito_rich': "COALESCE(r.num_credito_rich, 0)",
                'num_credito_dato': "COALESCE(r.num_credito_dato, 0)",
                'num_credito_dare': "COALESCE(r.num_credito_dare, 0)",
                'data_credito_rinnovo_rich': "r.data_credito_rinnovo_rich",
                'data_credito_rinnovo_dato': "r.data_credito_rinnovo_dato",
                'val_nc_rich': "COALESCE(r.val_nc_rich, 0)",
                'val_nc_dato': "COALESCE(r.val_nc_dato, 0)",
                'val_nc_saldo': "COALESCE(r.val_nc_saldo, 0)",
                'data_saldo': "r.data_saldo",
                'note': "r.note",
                'creato_il': "r.creato_il"
            }
            
            for col_name, sql_expr in col_map.items():
                if col_name in existing_cols:
                    select_parts.append(f"{sql_expr} as {col_name}")
                else:
                    print(f"[WARNING] Colonna '{col_name}' NON ESISTE, saltata")
            
            query = f"SELECT {', '.join(select_parts)} FROM rinnovi r ORDER BY r.creato_il DESC"
            print(f"[DEBUG] Query eseguita: {query[:200]}...")
            
            cur.execute(query)
            
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            
            print(f"[DB SUCCESS] Trovate {len(rows)} righe")
            
            result = []
            for row in rows:
                record = {}
                for idx, col_name in enumerate(col_names):
                    val = row[idx]
                    if val is None:
                        val = 0 if 'num_' in col_name or 'val_' in col_name else ""
                    record[col_name] = val
                result.append(record)
                
            print(f"[API SUCCESS] Restituiti {len(result)} record")
            return result
            
    except Exception as e:
        print(f"[ERRORE CRITICO] {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if conn:
            conn.close()

# ... (mantieni gli altri endpoint invariati) ...
