from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from config import TABELLE_COLONNE
from models import ListaPayload, OperatorePayload

router = APIRouter()

@router.get("/api/resellers")
def api_resellers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM resellers ORDER BY nominativo"); return cur.fetchall()
    finally: conn.close()

@router.get("/api/procuratori")
def api_procuratori(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM procuratori ORDER BY nominativo"); return cur.fetchall()
    finally: conn.close()

@router.get("/api/servers")
def api_servers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM servers ORDER BY nominativo"); return cur.fetchall()
    finally: conn.close()

@router.get("/api/dispositivi")
def api_dispositivi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM dispositivi ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@router.get("/api/sistemi_operativi")
def api_sistemi_operativi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM sistemi_operativi ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@router.get("/api/buffett")
def api_buffett():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM buffett ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@router.get("/api/metodi_pagamento")
def api_metodi_pagamento():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM metodi_pagamento ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@router.post("/api/lista/nuovo")
def api_lista_nuovo(payload: ListaPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(payload.tabella, 'nome')
            cur.execute(f"INSERT INTO {payload.tabella} ({col}) VALUES (%s)", (payload.nome,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@router.post("/api/lista/modifica")
def api_lista_modifica(id: int, nome: str, tabella: str, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(tabella, 'nome')
            cur.execute(f"UPDATE {tabella} SET {col} = %s WHERE id = %s", (nome, id))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@router.delete("/api/lista/cancella/{id}")
def api_lista_cancella(id: int, tabella: str, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {tabella} WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@router.get("/api/operatori_it")
def api_operatori_it(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM operatori_it ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@router.post("/api/operatori_it")
def api_operatori_it_nuovo(payload: OperatorePayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO operatori_it (nome) VALUES (%s)", (payload.dati.get("nome",""),))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@router.put("/api/operatori_it/{id}")
def api_operatori_it_modifica(id: int, payload: OperatorePayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE operatori_it SET nome = %s WHERE id = %s", (payload.dati.get("nome",""), id))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@router.delete("/api/operatori_it/{id}")
def api_operatori_it_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operatori_it WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}
