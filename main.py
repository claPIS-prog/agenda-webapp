import json
import urllib.request
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from db import ALL_MODULES, db_conn, estrai_dati, get_current_user, init_db
from routes.crediti import router as crediti_router

init_db()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(crediti_router)

# === PERMESSI / AMICI ===
@app.get("/api/amici")
def api_amici(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.telegram_id, a.password,
                       COALESCE(a.nome, n.nominativo) AS nome,
                       COALESCE(a.nome, n.nominativo) AS nominativo,
                       COALESCE(a.note, '') AS note
                FROM autorizzati a
                LEFT JOIN nominativi n ON n.id = a.id
                ORDER BY nome, a.id
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/lista_permessi")
def api_lista_permessi(q: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT a.id, a.telegram_id,
                       COALESCE(a.nome, n.nominativo, 'Utente #' || a.id::text) AS nome,
                       COALESCE(a.nome, n.nominativo, 'Utente #' || a.id::text) AS nominativo,
                       COALESCE(a.note, '') AS note
                FROM autorizzati a
                LEFT JOIN nominativi n ON n.id = a.id
                WHERE 1=1
            """
            params = []
            if q and q.strip():
                query += " AND (LOWER(COALESCE(a.nome, n.nominativo, '')) LIKE %s OR CAST(a.telegram_id AS TEXT) LIKE %s)"
                pattern = f"%{q.strip().lower()}%"
                params.extend([pattern, pattern])
            query += " ORDER BY nome, a.id"
            cur.execute(query, params)
            utenti = cur.fetchall()

            cur.execute("SELECT user_id, modulo, attivo FROM permessi")
            perm_rows = cur.fetchall()
            perms_by_user = {}
            for pr in perm_rows:
                uid = pr["user_id"]
                if uid not in perms_by_user:
                    perms_by_user[uid] = {mod: False for mod in ALL_MODULES}
                if pr["modulo"] in ALL_MODULES:
                    perms_by_user[uid][pr["modulo"]] = bool(pr["attivo"])

            risultato = []
            for u in utenti:
                uid = u["id"]
                mappa = perms_by_user.get(uid, {mod: False for mod in ALL_MODULES})
                attivi = [mod for mod, attivo in mappa.items() if attivo]
                risultato.append({
                    "id": uid,
                    "telegram_id": u["telegram_id"],
                    "nome": u["nome"],
                    "nominativo": u["nominativo"],
                    "note": u.get("note", ""),
                    "permessi": mappa,
                    "moduli_lista": attivi,
                    "moduli_attivi": len(attivi),
                    "totale_moduli_attivi": len(attivi)
                })
            return risultato
    finally:
        conn.close()

class AmicoPayload(BaseModel):
    id: int | None = None
    telegram_id: int | None = None
    password: str = ""
    nome: str = ""
    note: str = ""

@app.post("/api/salva_amico")
def api_salva_amico(payload: AmicoPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            target_id = payload.id if payload.id is not None else payload.telegram_id
            if target_id is None:
                raise HTTPException(status_code=400, detail="ID utente mancante")
            tg_id = payload.telegram_id if payload.telegram_id is not None else target_id
            cur.execute("SELECT id FROM autorizzati WHERE id = %s OR telegram_id = %s", (target_id, tg_id))
            exists = cur.fetchone()
            if exists:
                record_id = exists["id"]
                cur.execute("""
                    UPDATE autorizzati SET
                        telegram_id = %s,
                        password = %s,
                        nome = COALESCE(NULLIF(%s, ''), nome),
                        note = %s
                    WHERE id = %s
                """, (tg_id, payload.password, payload.nome, payload.note, record_id))
            else:
                cur.execute("""
                    INSERT INTO autorizzati (id, telegram_id, password, nome, note)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (target_id, tg_id, payload.password, payload.nome, payload.note))
                record_id = cur.fetchone()["id"]
                for mod in ALL_MODULES:
                    cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, FALSE) ON CONFLICT (user_id, modulo) DO NOTHING", (record_id, mod))
            conn.commit()
            return {"ok": True, "id": record_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO autorizzati (telegram_id, password, nome, note) VALUES (%s, %s, %s, %s) ON CONFLICT (telegram_id) DO UPDATE SET password = excluded.password, nome = excluded.nome, note = excluded.note RETURNING id", (payload.telegram_id, payload.password, payload.nome, payload.note))
            new_id = cur.fetchone()["id"]
            for mod in ALL_MODULES:
                cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, TRUE) ON CONFLICT (user_id, modulo) DO NOTHING", (new_id, mod))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/rimuovi_amico/{amico_id}")
def api_rimuovi_amico(amico_id: int, request: Request):
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

@app.get("/api/permessi/{user_id}")
def api_get_permessi(user_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {row["modulo"]: bool(row["attivo"]) for row in rows}
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            return {"permessi": perms}
    finally:
        conn.close()

@app.delete("/api/permessi/{user_id}")
def api_delete_permessi(user_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE permessi SET attivo = FALSE WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

class PermessiPayload(BaseModel):
    user_id: int
    permessi: dict

@app.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            for modulo, attivo in payload.permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, %s) ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = excluded.attivo", (payload.user_id, modulo, bool(attivo)))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === NOMINATIVI / LISTA ===
@app.get("/api/nominativi")
def api_nominativi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, tipo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/contatti")
def api_contatti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, tipo, prezzo, cadenza, tipo_linea, dispositivo, sistema_operativo, buffett, metodo_pagamento, operatore_it FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/api/azione")
async def api_azione(request: Request):
    get_current_user(request)
    dati = estrai_dati(await request.json())
    azione = dati.get("azione", "")
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if azione == "cancella":
                cur.execute("DELETE FROM nominativi WHERE id = %s", (dati.get("id"),))
            elif azione == "nuovo":
                cur.execute("""INSERT INTO nominativi 
                    (nominativo, tipo, user_id, password, prezzo, cadenza, tipo_linea, server, reseller, 
                     dispositivo, sistema_operativo, buffett, metodo_pagamento, operatore_it, 
                     cellulare, procuratore, apk_utilizzata, uso_vpn, quale_vpn, citta, 
                     data_iscrizione, data_fine, informazioni) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                    (dati.get("nominativo",""), dati.get("tipo",""), dati.get("user_id",""), dati.get("password",""), 
                     float(dati.get("prezzo",0) or 0), dati.get("cadenza",""), dati.get("tipo_linea",""), 
                     dati.get("server",""), dati.get("reseller",""),
                     dati.get("dispositivo",""), dati.get("sistema_operativo",""),
                     dati.get("buffett",""), dati.get("metodo_pagamento",""), dati.get("operatore_it",""),
                     dati.get("cellulare",""), dati.get("procuratore",""),
                     dati.get("apk_utilizzata",""), int(dati.get("uso_vpn",0) or 0),
                     dati.get("quale_vpn",""), dati.get("citta",""),
                     dati.get("data_iscrizione",""), dati.get("data_fine",""),
                     dati.get("informazioni","")))
            elif azione == "modifica":
                cur.execute("""UPDATE nominativi SET 
                    nominativo=%s, tipo=%s, user_id=%s, password=%s, prezzo=%s, cadenza=%s, tipo_linea=%s, 
                    server=%s, reseller=%s, dispositivo=%s, sistema_operativo=%s, 
                    buffett=%s, metodo_pagamento=%s, operatore_it=%s, cellulare=%s, procuratore=%s, 
                    apk_utilizzata=%s, uso_vpn=%s, quale_vpn=%s, citta=%s, 
                    data_iscrizione=%s, data_fine=%s, informazioni=%s WHERE id=%s""", 
                    (dati.get("nominativo"), dati.get("tipo"), dati.get("user_id"), dati.get("password"), 
                     float(dati.get("prezzo",0) or 0), dati.get("cadenza"), dati.get("tipo_linea"), 
                     dati.get("server"), dati.get("reseller"),
                     dati.get("dispositivo"), dati.get("sistema_operativo"),
                     dati.get("buffett"), dati.get("metodo_pagamento"), dati.get("operatore_it"),
                     dati.get("cellulare"), dati.get("procuratore"),
                     dati.get("apk_utilizzata"), int(dati.get("uso_vpn",0) or 0),
                     dati.get("quale_vpn"), dati.get("citta"),
                     dati.get("data_iscrizione"), dati.get("data_fine"),
                     dati.get("informazioni"), dati.get("id")))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === SCADENZE & RINNOVI ===
@app.get("/api/scadenze")
def api_scadenze(request: Request):
    get_current_user(request)
    oggi = datetime.now().date()
    limite = oggi + timedelta(days=7)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.scadenza ASC")
            rows = cur.fetchall()
            out = []
            for r in rows:
                scad = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        scad = datetime.strptime(r["scadenza"], fmt).date()
                        break
                    except Exception:
                        pass
                if scad and scad <= limite:
                    delta = (scad - oggi).days
                    out.append({"id": r["id"], "nominativo_id": r["nominativo_id"], "nominativo": r["nominativo"], "scadenza": r["scadenza"], "orario_scadenza": r.get("orario_scadenza",""), "scaduta": delta < 0, "giorni": delta})
            return out
    finally:
        conn.close()

@app.get("/api/elenco_rinnovi")
@app.get("/api/lista_rinnovi")
def api_elenco_rinnovi(q: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT r.id, r.nominativo_id, r.tipo, r.data_operazione, r.mesi, r.scadenza,
                       r.orario_scadenza, r.importo_acconto, r.importo_saldo, r.data_acconto,
                       r.data_saldo, r.note, r.creato_il, r.num_credito_rich, r.num_credito_dato,
                       r.num_credito_dare, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato,
                       r.val_singolo_nc_rich, r.val_nc_rich, n.nominativo
                FROM rinnovi r
                JOIN nominativi n ON n.id = r.nominativo_id
                WHERE 1=1
            """
            params = []
            if q and q.strip():
                query += " AND LOWER(n.nominativo) LIKE %s"
                params.append(f"%{q.strip().lower()}%")
            query += " ORDER BY COALESCE(r.creato_il, '') DESC, r.id DESC"
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/api/rinnovo")
async def api_rinnovo(request: Request):
    get_current_user(request)
    dati = estrai_dati(await request.json())
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            num_rich = int(dati.get("num_credito_rich", 0) or 0)
            num_dato = int(dati.get("num_credito_dato", 0) or 0)
            val_singolo = float(dati.get("val_singolo_nc_rich", 0) or 0)
            cur.execute("INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, orario_scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il, num_credito_rich, num_credito_dato, num_credito_dare, data_credito_rinnovo_rich, data_credito_rinnovo_dato, val_singolo_nc_rich, val_nc_rich) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (int(dati.get("nominativo_id")), dati.get("tipo","rinnovo"), dati.get("data_operazione"), num_rich, dati.get("scadenza"), dati.get("orario_scadenza",""), float(dati.get("importo_acconto",0) or 0), float(dati.get("importo_saldo",0) or 0), datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_acconto",0) or 0)>0 else "", datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_saldo",0) or 0)>0 else "", dati.get("note",""), datetime.now().isoformat(), num_rich, num_dato, num_rich - num_dato, dati.get("data_credito_rinnovo_rich",""), dati.get("data_credito_rinnovo_dato",""), val_singolo, num_rich * val_singolo))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/rinnovo/{id}")
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

# === LISTE DI SUPPORTO ===
@app.get("/api/resellers")
def api_resellers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM resellers ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/procuratori")
def api_procuratori(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM procuratori ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/servers")
def api_servers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM servers ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/dispositivi")
def api_dispositivi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM dispositivi ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/sistemi_operativi")
def api_sistemi_operativi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM sistemi_operativi ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/buffett")
def api_buffett():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM buffett ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/metodi_pagamento")
def api_metodi_pagamento():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM metodi_pagamento ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

TABELLE_COLONNE = {'dispositivi':'nome','sistemi_operativi':'nome','buffett':'nome','metodi_pagamento':'nome','resellers':'nominativo','servers':'nominativo','procuratori':'nominativo','operatori_it':'nome'}

class ListaPayload(BaseModel):
    nome: str
    tabella: str

@app.post("/api/lista/nuovo")
def api_lista_nuovo(payload: ListaPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(payload.tabella, 'nome')
            cur.execute(f"INSERT INTO {payload.tabella} ({col}) VALUES (%s)", (payload.nome,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.post("/api/lista/modifica")
def api_lista_modifica(id: int, nome: str, tabella: str, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(tabella, 'nome')
            cur.execute(f"UPDATE {tabella} SET {col} = %s WHERE id = %s", (nome, id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/lista/cancella/{id}")
def api_lista_cancella(id: int, tabella: str, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {tabella} WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === NOTE ===
@app.get("/api/note")
def api_note(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT n.id, n.nominativo_id, n.messaggio, n.creato_il, nom.nominativo FROM note n JOIN nominativi nom ON nom.id = n.nominativo_id ORDER BY COALESCE(n.creato_il, '') DESC, n.id DESC")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/api/note")
async def api_note_nuovo(request: Request):
    get_current_user(request)
    dati = estrai_dati(await request.json())
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note (nominativo_id, messaggio, creato_il) VALUES (%s,%s,%s)", (int(dati.get("nominativo_id")), dati.get("messaggio",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/note/{id}")
def api_note_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM note WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === CREDENZIALI ===
@app.get("/api/credenziali")
def api_credenziali(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, nome_file, link, percorso, user_id, password, file_token, scadenza, informazioni, creato_il FROM credenziali ORDER BY COALESCE(creato_il, '') DESC, id DESC")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/api/credenziali")
async def api_credenziali_nuovo(request: Request):
    get_current_user(request)
    d = estrai_dati(await request.json())
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO credenziali (nominativo, nome_file, link, percorso, user_id, password, file_token, scadenza, informazioni, creato_il) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (d.get("nominativo",""),d.get("nome_file",""),d.get("link",""),d.get("percorso",""),d.get("user_id",""),d.get("password",""),d.get("file_token",""),d.get("scadenza",""),d.get("informazioni",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.put("/api/credenziali/{id}")
async def api_credenziali_modifica(id: int, request: Request):
    get_current_user(request)
    d = estrai_dati(await request.json())
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE credenziali SET nominativo=%s, nome_file=%s, link=%s, percorso=%s, user_id=%s, password=%s, file_token=%s, scadenza=%s, informazioni=%s WHERE id=%s", (d.get("nominativo",""),d.get("nome_file",""),d.get("link",""),d.get("percorso",""),d.get("user_id",""),d.get("password",""),d.get("file_token",""),d.get("scadenza",""),d.get("informazioni",""), id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/credenziali/{id}")
def api_credenziali_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT file_token, percorso FROM credenziali WHERE id = %s", (id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Record non trovato")
            if item['percorso'] and item['file_token']:
                try:
                    cur.execute("SELECT user_id, password FROM credenziali WHERE id = %s", (id,))
                    creds = cur.fetchone()
                    if creds:
                        body = json.dumps({"token": item['file_token'], "user": creds['user_id'], "password": creds['password']}).encode('utf-8')
                        req = urllib.request.Request(item['percorso'], data=body, method='POST')
                        req.add_header('Content-Type', 'application/json')
                        urllib.request.urlopen(req, timeout=5)
                except Exception as e:
                    print(f"Avviso cancellazione remota: {e}")
            cur.execute("DELETE FROM credenziali WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)