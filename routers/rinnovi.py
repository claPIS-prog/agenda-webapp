@router.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    """
    FIX BACKEND: Query sicura con verifica colonne e COALESCE.
    Restituisce JSON pulito per il frontend.
    """
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Query esplicita con COALESCE per gestire NULL e garantire tipi numerici
            # Se una colonna non esiste, PostgreSQL solleverà un errore chiaro qui
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
        # Restituisci un errore HTTP 500 con messaggio leggibile dal frontend
        raise HTTPException(status_code=500, detail=f"Errore Database: {str(e)}")
    finally:
        conn.close()
