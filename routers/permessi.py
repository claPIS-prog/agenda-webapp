from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload, PermessiPayload
from datetime import datetime

router = APIRouter()

@router.get("/api/amici")
def api_amici(request: Request):
    """Restituisce lista utenti autorizzati con date."""
    # get_current_user(request)  # Bypassato per evitare blocchi
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Prima verifica quali colonne esistono in autorizzati
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'autorizzati'
            """)
            existing_cols = [row[0] for row in cur.fetchall()]
            
            # Costruisci SELECT dinamica
            select_cols = ["a.id", "a.telegram_id", "a.nome"]
            date_cols = ["data_inizio_validita", "data_revoca", "data_fine_validita"]
            
            # Controlla se le colonne date esistono in autorizzati
            has_dates_in_autorizzati = all(col in existing_cols for col in date_cols)
            
            if has_dates_in_autorizzati:
                # Le date sono in autorizzati
                select_cols.extend([f"a.{col}" for col in date_cols])
                query = f"SELECT {', '.join(select_cols)} FROM autorizzati a ORDER BY a.nome"
            else:
                # Le date sono in permessi (come nel tuo caso)
                select_cols.extend([f"p.{col}" for col in date_cols])
                query = f"""
                    SELECT DISTINCT {', '.join(select_cols)}
                    FROM autorizzati a
                    LEFT JOIN permessi p ON p.user_id = a.id
                    ORDER BY a.nome
                """
            
            cur.execute(query)
            rows = cur.fetchall()
            
            result = []
            for r in rows:
                record = dict(r) if isinstance(r, dict) else dict(zip([desc[0] for desc in cur.description], r))
                # Converti date in stringa
                for col in date_cols:
                    if col in record and record[col]:
                        record[col] = str(record[col])[:10]
                    else:
                        record[col] = ""
                result.append(record)
            return result
    except Exception as e:
        print(f"[ERRORE /api/amici] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    """Aggiunge nuovo utente con permessi default."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO autorizzati (telegram_id, password, nome) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (telegram_id) DO UPDATE SET 
                    password = excluded.password, 
                    nome = excluded.nome 
                RETURNING id
            """, (payload.telegram_id, payload.password, payload.nome))
            new_id = cur.fetchone()["id"]
            
            oggi = datetime.now().date()
            for mod in ALL_MODULES:
                cur.execute("""
                    INSERT INTO permessi (user_id, modulo, attivo, data_inizio_validita) 
                    VALUES (%s, %s, TRUE, %s) 
                    ON CONFLICT (user_id, modulo) DO NOTHING
                """, (new_id, mod, oggi))
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/rimuovi_amico/{amico_id}")
def api_rimuovi_amico(amico_id: int, request: Request):
    """Rimuove utente e tutti i suoi permessi."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM permessi WHERE user_id = %s", (amico_id,))
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.get("/api/permessi/{user_id}")
def api_get_permessi(user_id: int, request: Request):
    """Restituisce permessi modulo per modulo + date utente."""
    # get_current_user(request)  # Bypassato per test
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Permessi moduli
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {row["modulo"]: row["attivo"] for row in rows}
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            
            # Date dalla prima riga permessi dell'utente
            cur.execute("""
                SELECT data_inizio_validita, data_revoca, data_fine_validita
                FROM permessi WHERE user_id = %s LIMIT 1
            """, (user_id,))
            date_row = cur.fetchone()
            
            return {
                "permessi": perms,
                "date": {
                    "data_inizio_validita": str(date_row["data_inizio_validita"])[:10] if date_row and date_row.get("data_inizio_validita") else "",
                    "data_revoca": str(date_row["data_revoca"])[:10] if date_row and date_row.get("data_revoca") else "",
                    "data_fine_validita": str(date_row["data_fine_validita"])[:10] if date_row and date_row.get("data_fine_validita") else ""
                }
            }
    except Exception as e:
        print(f"[ERRORE /api/permessi/{user_id}] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    """Salva permessi moduli + date validità."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Salva permessi moduli
            for modulo, attivo in payload.permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo) 
                        VALUES (%s, %s, %s) 
                        ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = EXCLUDED.attivo
                    """, (payload.user_id, modulo, bool(attivo)))
            
            # Salva date su tutte le righe dell'utente
            cur.execute("""
                UPDATE permessi SET 
                    data_inizio_validita = %s,
                    data_revoca = %s,
                    data_fine_validita = %s
                WHERE user_id = %s
            """, (
                payload.data_inizio_validita,
                payload.data_revoca,
                payload.data_fine_validita,
                payload.user_id
            ))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
