from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload, PermessiPayload
from datetime import datetime

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. DROPDOWN NOMINATIVI (Tutti i clienti potenziali)
# -----------------------------------------------------------------------------
@router.get("/api/nominativi")
def api_nominativi(request: Request):
    """Restituisce TUTTI i nominativi per la selezione nella dropdown."""
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Legge dalla tabella 'nominativi' che contiene tutti i clienti
            cur.execute("SELECT id, nominativo as nome FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 2. GRIGLIA AMICI (Solo chi ha credenziali in 'autorizzati')
# -----------------------------------------------------------------------------
@router.get("/api/amici")
def api_amici(request: Request):
    """Restituisce SOLO gli utenti che hanno un record in autorizzati."""
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Join per avere il nome completo dal nominativo se manca in autorizzati
            cur.execute("""
                SELECT a.id, a.telegram_id, a.password, 
                       COALESCE(a.nome, n.nominativo) as nome
                FROM autorizzati a
                LEFT JOIN nominativi n ON n.id = a.id
                ORDER BY nome
            """)
            rows = cur.fetchall()
            result = []
            for r in rows:
                record = dict(r) if isinstance(r, dict) else dict(zip([desc[0] for desc in cur.description], r))
                result.append(record)
            return result
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 3. DATI SINGOLO AMICO (Per pre-popolare il form di modifica)
# -----------------------------------------------------------------------------
@router.get("/api/amici/{user_id}")
def api_get_amico(user_id: int, request: Request):
    """Recupera ID e Password di un specifico nominativo se esiste in autorizzati."""
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id, password FROM autorizzati WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                d = dict(row) if isinstance(row, dict) else dict(zip(["telegram_id", "password"], row))
                return d
            return {"telegram_id": None, "password": None}
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 4. SALVA / AGGIORNA AMICO
# -----------------------------------------------------------------------------
@router.post("/api/salva_amico")
def api_salva_amico(payload: AmicoPayload, request: Request):
    """Crea o aggiorna un amico in autorizzati usando l'ID del nominativo."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # payload.telegram_id qui rappresenta l'ID del nominativo selezionato
            user_id = payload.telegram_id 
            
            # Verifica se esiste già in autorizzati
            cur.execute("SELECT id FROM autorizzati WHERE id = %s", (user_id,))
            exists = cur.fetchone()
            
            if exists:
                cur.execute("""
                    UPDATE autorizzati SET 
                        telegram_id = %s, 
                        password = %s, 
                        nome = %s 
                    WHERE id = %s
                """, (user_id, payload.password, payload.nome, user_id))
            else:
                cur.execute("""
                    INSERT INTO autorizzati (id, telegram_id, password, nome)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, user_id, payload.password, payload.nome))
                
                # Crea permessi default disattivati per il nuovo utente
                for mod in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo)
                        VALUES (%s, %s, FALSE)
                        ON CONFLICT (user_id, modulo) DO NOTHING
                    """, (user_id, mod))
            
            conn.commit()
            return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 5. ELIMINA AMICO
# -----------------------------------------------------------------------------
@router.delete("/api/amici/{amico_id}")
def api_elimina_amico(amico_id: int, request: Request):
    """Rimuove un amico e i suoi permessi."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM permessi WHERE user_id = %s", (amico_id,))
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
            conn.commit()
            return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 6. PERMESSI UTENTE (Mantenuto per compatibilità con altri form)
# -----------------------------------------------------------------------------
@router.get("/api/permessi/{user_id}")
def api_get_permessi(user_id: int, request: Request):
    """Restituisce permessi modulo per modulo + date utente."""
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {}
            for row in rows:
                d = dict(row) if isinstance(row, dict) else dict(zip(["modulo", "attivo"], row))
                perms[d["modulo"]] = d["attivo"]
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            
            cur.execute("""
                SELECT data_inizio_validita, data_revoca, data_fine_validita
                FROM permessi WHERE user_id = %s LIMIT 1
            """, (user_id,))
            date_row = cur.fetchone()
            
            dates = {"data_inizio_validita": "", "data_revoca": "", "data_fine_validita": ""}
            if date_row:
                d = dict(date_row) if isinstance(date_row, dict) else dict(zip(
                    ["data_inizio_validita", "data_revoca", "data_fine_validita"], date_row
                ))
                for k in dates:
                    if d.get(k):
                        dates[k] = str(d[k])[:10]
            
            return {"permessi": perms, "date": dates}
    finally:
        conn.close()

@router.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    """Salva permessi moduli + date validità."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM autorizzati WHERE id = %s", (payload.user_id,))
            if not cur.fetchone():
                cur.execute("SELECT nominativo FROM nominativi WHERE id = %s", (payload.user_id,))
                nom = cur.fetchone()
                nome = nom["nominativo"] if nom else f"Nominativo #{payload.user_id}"
                cur.execute("""
                    INSERT INTO autorizzati (id, telegram_id, password, nome)
                    VALUES (%s, %s, 'auto', %s)
                    ON CONFLICT (id) DO NOTHING
                """, (payload.user_id, -payload.user_id, nome))

            for modulo, attivo in payload.permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = EXCLUDED.attivo
                    """, (payload.user_id, modulo, bool(attivo)))

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
