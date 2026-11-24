from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload

router = APIRouter()

@router.get("/api/scadenze")
def api_scadenze(request: Request):
    get_current_user(request)
    oggi = datetime.now().date()
    limite_futuro = oggi + timedelta(days=7) 
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo 
                FROM rinnovi r 
                JOIN nominativi n ON n.id = r.nominativo_id 
                WHERE r.scadenza::date <= %s
                AND NOT EXISTS (
                    SELECT 1 FROM rinnovi r2 
                    WHERE r2.nominativo_id = r.nominativo_id 
                    AND r2.data_operazione > r.data_operazione
                    AND r2.scadenza::date > %s
                )
                ORDER BY r.scadenza ASC
            """, (limite_futuro.isoformat(), oggi.isoformat()))
            rows = cur.fetchall()
            out = []
            for r in rows:
                scad_date = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        scad_date = datetime.strptime(r["scadenza"], fmt).date()
                        break
                    except: pass
                if not scad_date: continue
                delta = (scad_date - oggi).days
                out.append({
                    "id": r["id"], "nominativo_id": r["nominativo_id"], 
                    "nominativo": r["nominativo"], "scadenza": r["scadenza"], 
                    "orario_scadenza": r.get("orario_scadenza",""), 
                    "scaduta": delta < 0, "giorni": delta
                })
            return out
    finally:
        conn.close()

@router.get("/api/crediti_disponibili")
def api_crediti_disponibili(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, 'Saldo Storico' as tipo, quantita, valore, data_acquisto as data_ref 
                FROM crediti WHERE quantita > 0
                UNION ALL
                SELECT id, 'Nuovo Acquisto', quantita, valore, data_acquisto 
                FROM crediti ORDER BY data_ref DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

@router.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # FIX: Inclusi user_id e password nella SELECT per poterli mostrare/modificare
            cur.execute("SELECT r.id, r.nominativo_id, r.tipo, r.data_operazione, r.mesi, r.scadenza, r.orario_scadenza, r.importo_acconto, r.importo_saldo, r.data_acconto, r.data_saldo, r.note, r.creato_il, r.num_credito_rich, r.num_credito_dato, r.num_credito_dare, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato, r.val_singolo_nc_rich, r.val_nc_rich, r.credito_id, n.nominativo, n.user_id, n.password FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.creato_il DESC")
            return cur.fetchall()
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
            # FIX: Gestione esplicita della modifica rinnovo con UserID/Password
            if azione == "modifica_rinnovo":
                cur.execute("""
                    UPDATE rinnovi SET 
                        nominativo_id=%s, tipo=%s, data_operazione=%s, scadenza=%s, 
                        importo_acconto=%s, importo_saldo=%s, note=%s 
                    WHERE id=%s
                """, (
                    int(dati.get("nominativo_id")), dati.get("tipo"), 
                    dati.get("data_operazione"), dati.get("scadenza"),
                    float(dati.get("importo_acconto",0)), float(dati.get("importo_saldo",0)),
                    dati.get("note",""), int(dati.get("id"))
                ))
                # Aggiorna anche UserID/Password sul nominativo collegato se forniti
                if dati.get("user_id") is not None or dati.get("password") is not None:
                    cur.execute("""
                        UPDATE nominativi SET user_id=%s, password=%s WHERE id=%s
                    """, (dati.get("user_id",""), dati.get("password",""), int(dati.get("nominativo_id"))))
            
            elif azione == "nuovo" or azione == "rinnovo":
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
    finally:
        conn.close()
    return {"ok": True}

@router.get("/api/pagamenti_sospesi")
def api_pagamenti_sospesi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id, n.nominativo, r.data_operazione, r.data_acconto, 
                       r.importo_acconto, r.importo_saldo, 
                       (r.importo_saldo - r.importo_acconto) as sospeso
                FROM rinnovi r
                JOIN nominativi n ON n.id = r.nominativo_id
                WHERE r.importo_saldo > r.importo_acconto
                ORDER BY r.data_operazione DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()
