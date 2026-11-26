from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload
from datetime import datetime

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. DROPDOWN NOMINATIVI (Tutti i clienti potenziali)
# -----------------------------------------------------------------------------
@router.get("/api/nominativi")
def api_nominativi(request: Request):
    """Restituisce TUTTI i nominativi per la selezione."""
    conn = db_conn()
    try:
        with conn.cursor() as cur:
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
            # Leggiamo solo da autorizzati. Se vuoi il nome completo, facciamo join con nominativi
            # Assumendo che autorizzati abbia un campo 'nome' o 'telegram_id' collegabile
            # Per sicurezza, leggiamo direttamente da autorizzati come fonte di verità degli "Amici"
            cur.execute("""
                SELECT a.id, a.telegram_id, a.password, a.nome 
                FROM autorizzati a
                ORDER BY a.nome
            """)
            rows = cur.fetchall()
            result = []
            for r in rows:
                record = dict(r) if isinstance(r, dict) else dict(zip([desc[0] for desc in cur.description], r))
                # Pulizia dati sensibili se necessario, ma qui servono per edit
                result.append(record)
            return result
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 3. DATI SINGOLO AMICO (Per pre-popolare il form)
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
    """Crea o aggiorna un amico in autorizzati."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Verifica se esiste già
            cur.execute("SELECT id FROM autorizzati WHERE id = %s", (payload.telegram_id,)) # Usiamo telegram_id come chiave univoca o ID? 
            # Nota: Nel tuo modello AmicoPayload c'è telegram_id. 
            # Se stai usando l'ID del nominativo come ID utente, dobbiamo adattare.
            # Assumo che tu voglia usare l'ID del nominativo come ID in autorizzati.
            
            # Controllo esistenza per ID nominativo
            cur.execute("SELECT id FROM autorizzati WHERE id = %s", (payload.telegram_id,)) 
            # ATTENZIONE: payload.telegram_id qui rappresenta l'ID del nominativo selezionato
            
            exists = cur.fetchone()
            
            if exists:
                cur.execute("""
                    UPDATE autorizzati SET 
                        telegram_id = %s, 
                        password = %s, 
                        nome = %s 
                    WHERE id = %s
                """, (payload.telegram_id, payload.password, payload.nome, payload.telegram_id))
            else:
                cur.execute("""
                    INSERT INTO autorizzati (id, telegram_id, password, nome)
                    VALUES (%s, %s, %s, %s)
                """, (payload.telegram_id, payload.telegram_id, payload.password, payload.nome))
                
                # Crea permessi default disattivati
                for mod in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo)
                        VALUES (%s, %s, FALSE)
                        ON CONFLICT (user_id, modulo) DO NOTHING
                    """, (payload.telegram_id, mod))
            
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
