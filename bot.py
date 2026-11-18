import os
import sqlite3
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTHORIZED_IDS = [int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x]
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "")
DB_FILE = os.getenv("DB_FILE", "agenda.db")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN mancante")

WEBAPP_URL = "https://agenda-webapp.onrender.com/index.html"
LISTA_WEBAPP_URL = "https://agenda-webapp.onrender.com/elencazione.html"
SCADENZE_WEBAPP_URL = "https://agenda-webapp.onrender.com/scadenze.html"
RINNOVI_WEBAPP_URL = "https://agenda-webapp.onrender.com/rinnovi.html"
RINNOVI_LISTA_WEBAPP_URL = "https://agenda-webapp.onrender.com/rinnovi_lista.html"
RESELLER_WEBAPP_URL = "https://agenda-webapp.onrender.com/reseller.html"
PROCURATORI_WEBAPP_URL = "https://agenda-webapp.onrender.com/procuratori.html"
SERVER_WEBAPP_URL = "https://agenda-webapp.onrender.com/server.html"
NOTE_WEBAPP_URL = "https://claPIS-prog.github.io/agenda-webapp/note.html"
APK_WEBAPP_URL = "https://agenda-webapp.onrender.com/apk.html"
EXTRA_WEBAPP_URL = "https://agenda-webapp.onrender.com/amici.html"
DISPOSITIVI_WEBAPP_URL = "https://agenda-webapp.onrender.com/dispositivi.html"
SISTEMI_OP_WEBAPP_URL = "https://agenda-webapp.onrender.com/sistemi_operativi.html"
BUFFETT_WEBAPP_URL = "https://agenda-webapp.onrender.com/buffett.html"
PAGAMENTI_WEBAPP_URL = "https://agenda-webapp.onrender.com/metodi_pagamento.html"
NOTIFICHE_WEBAPP_URL = "https://agenda-webapp.onrender.com/notifiche.html"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

_utenti_sbloccati = {}

def is_unlocked(user_id):
    return _utenti_sbloccati.get(user_id, False)

def unlock_user(user_id):
    _utenti_sbloccati[user_id] = True

def db_init():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS nominativi (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nominativo TEXT NOT NULL, user_id TEXT, password TEXT,
        cellulare TEXT, whatsapp TEXT, server TEXT, reseller TEXT, procuratore TEXT,
        uso_vpn INTEGER DEFAULT 0, quale_vpn TEXT, residenza TEXT, applicazioni TEXT,
        dispositivi TEXT, pacchetto TEXT, fornitore TEXT, tipo_pagamento TEXT,
        prezzo REAL DEFAULT 0, cadenza TEXT, tipo_linea TEXT, data_iscrizione TEXT,
        creato_il TEXT, tipo TEXT, sistema_operativo TEXT, buffett TEXT, metodo_pagamento TEXT)""")
    conn.commit()
    conn.close()

def authorized(update):
    if AUTHORIZED_IDS and update.effective_user.id not in AUTHORIZED_IDS:
        return False
    return True

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await update.message.reply_text("⛔ Non sei autorizzato.")
        return
    if not is_unlocked(update.effective_user.id):
        await update.message.reply_text("🔐 Inserisci la password:")
        ctx.user_data["attesa_password"] = True
        return
    await update.message.reply_text("👋 Benvenuto!")
    await mostra_menu(update, ctx)

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not is_unlocked(update.effective_user.id):
        await update.message.reply_text("🔐 Inserisci la password:")
        ctx.user_data["attesa_password"] = True
        return
    await mostra_menu(update, ctx)

async def mostra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update) or not is_unlocked(update.effective_user.id):
        return
    keyboard = [
        [KeyboardButton("📝 Nominativo", web_app=WebAppInfo(url=WEBAPP_URL)), KeyboardButton("📋 Lista", web_app=WebAppInfo(url=LISTA_WEBAPP_URL)), KeyboardButton("⏰ Scadenze", web_app=WebAppInfo(url=SCADENZE_WEBAPP_URL))],
        [KeyboardButton("🔄 Rinnovi", web_app=WebAppInfo(url=RINNOVI_WEBAPP_URL)), KeyboardButton("📜 Storico Rinnovi", web_app=WebAppInfo(url=RINNOVI_LISTA_WEBAPP_URL)), KeyboardButton("🏢 Reseller", web_app=WebAppInfo(url=RESELLER_WEBAPP_URL))],
        [KeyboardButton("⚖️ Procuratori", web_app=WebAppInfo(url=PROCURATORI_WEBAPP_URL)), KeyboardButton("🖥️ Server", web_app=WebAppInfo(url=SERVER_WEBAPP_URL)), KeyboardButton("💬 Nota", web_app=WebAppInfo(url=NOTE_WEBAPP_URL))],
        [KeyboardButton("📥 APK", web_app=WebAppInfo(url=APK_WEBAPP_URL)), KeyboardButton("👥 Extra", web_app=WebAppInfo(url=EXTRA_WEBAPP_URL)), KeyboardButton("📱 Dispositivi", web_app=WebAppInfo(url=DISPOSITIVI_WEBAPP_URL))],
        [KeyboardButton("💻 Sistemi Op.", web_app=WebAppInfo(url=SISTEMI_OP_WEBAPP_URL)), KeyboardButton("🍔 Buffett", web_app=WebAppInfo(url=BUFFETT_WEBAPP_URL)), KeyboardButton("💳 Pagamenti", web_app=WebAppInfo(url=PAGAMENTI_WEBAPP_URL))],
        [KeyboardButton("🔔 Notifiche", web_app=WebAppInfo(url=NOTIFICHE_WEBAPP_URL))]
    ]
    await update.message.reply_text("Seleziona un'operazione:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def ricevi_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("attesa_password"):
        return
    uid = update.effective_user.id
    pw = update.message.text.strip()
    ok = False
    if AUTHORIZED_IDS and uid in AUTHORIZED_IDS:
        ok = (pw == BOT_PASSWORD)
    else:
        ok = (pw == BOT_PASSWORD)
    
    if ok:
        unlock_user(uid)
        ctx.user_data["attesa_password"] = False
        await update.message.reply_text("✅ Password corretta!")
        await mostra_menu(update, ctx)
    else:
        await update.message.reply_text("❌ Password errata.")
        ctx.user_data["attesa_password"] = False

async def ricevi_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    try:
        dati = json.loads(update.message.web_app_data.data)
    except Exception:
        return await update.message.reply_text("❌ Dati non validi.")
    
    azione = dati.get("azione", "nuovo")
    conn = sqlite3.connect(DB_FILE)
    try:
        if azione == "nuovo":
            conn.execute("""INSERT INTO nominativi (nominativo, prezzo, cadenza, tipo, dispositivo, sistema_operativo, buffett, metodo_pagamento, data_iscrizione, creato_il) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (dati.get("nominativo",""), float(dati.get("prezzo",0)), dati.get("cadenza",""),
                 dati.get("tipo",""), dati.get("dispositivo",""), dati.get("sistema_operativo",""),
                 dati.get("buffett",""), dati.get("metodo_pagamento",""),
                 datetime.now().strftime("%d/%m/%Y"), datetime.now().isoformat()))
            msg = f"✅ Nominativo salvato: {dati.get('nominativo')}"
        elif azione == "cancella":
            conn.execute("DELETE FROM nominativi WHERE id = ?", (dati.get("id"),))
            msg = "✅ Nominativo cancellato."
        elif azione == "modifica":
            conn.execute("""UPDATE nominativi SET nominativo=?, prezzo=?, cadenza=?, tipo=?, dispositivo=?, sistema_operativo=?, buffett=?, metodo_pagamento=? WHERE id=?""",
                (dati.get("nominativo"), float(dati.get("prezzo",0)), dati.get("cadenza"),
                 dati.get("tipo"), dati.get("dispositivo"), dati.get("sistema_operativo"),
                 dati.get("buffett"), dati.get("metodo_pagamento"), dati.get("id")))
            msg = "✅ Nominativo aggiornato."
        else:
            msg = "✅ Dati ricevuti."
        conn.commit()
    finally:
        conn.close()
    await update.message.reply_text(msg)
    await mostra_menu(update, ctx)

def main():
    db_init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_password))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, ricevi_webapp_data))
    print("✅ Bot avviato!")
    app.run_polling()

if __name__ == "__main__":
    main()