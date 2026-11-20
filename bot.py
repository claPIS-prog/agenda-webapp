import os
import logging
import zipfile
import datetime
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, WebAppInfo, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTHORIZED_IDS = [int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x]
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "claudiopiscopo@gmail.com")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN mancante")

# URLS PRINCIPALI
WEBAPP_URL = "https://agenda-webapp.onrender.com/index.html"
LISTA_WEBAPP_URL = "https://agenda-webapp.onrender.com/elencazione.html"
SCADENZE_WEBAPP_URL = "https://agenda-webapp.onrender.com/scadenze.html"
RINNOVI_WEBAPP_URL = "https://agenda-webapp.onrender.com/rinnovi.html"
RINNOVI_LISTA_WEBAPP_URL = "https://agenda-webapp.onrender.com/rinnovi_lista.html"
SALDO_RINNOVI_WEBAPP_URL = "https://agenda-webapp.onrender.com/saldo_rinnovi.html"
NOTE_WEBAPP_URL = "https://agenda-webapp.onrender.com/note.html"
CREDENZIALI_WEBAPP_URL = "https://agenda-webapp.onrender.com/credenziali.html"
PERMESSI_WEBAPP_URL = "https://agenda-webapp.onrender.com/permessi.html"
TABELLE_WEBAPP_URL = "https://agenda-webapp.onrender.com/tabelle.html"

user_state = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_IDS:
        await update.message.reply_text("⛔ Non sei autorizzato.")
        return
    user_state[user_id] = 'waiting_password'
    await update.message.reply_text("🔒 Inserisci la password:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if user_state.get(user_id) == 'waiting_password':
        if text == BOT_PASSWORD:
            user_state[user_id] = 'authenticated'
            await update.message.reply_text("✅ Password corretta!", reply_markup=get_main_keyboard())
            await update.message.reply_text("Seleziona un'operazione:")
        else:
            await update.message.reply_text("❌ Password errata.")
        return

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📝 Nominativo", web_app=WebAppInfo(url=WEBAPP_URL)),
         KeyboardButton("📋 Lista", web_app=WebAppInfo(url=LISTA_WEBAPP_URL)),
         KeyboardButton("⏰ Scadenze", web_app=WebAppInfo(url=SCADENZE_WEBAPP_URL))],
        [KeyboardButton("🔄 Rinnovi", web_app=WebAppInfo(url=RINNOVI_WEBAPP_URL)),
         KeyboardButton("📜 Storico Rinnovi", web_app=WebAppInfo(url=RINNOVI_LISTA_WEBAPP_URL)),
         KeyboardButton("📊 Saldo Rinnovi", web_app=WebAppInfo(url=SALDO_RINNOVI_WEBAPP_URL))],
        [KeyboardButton("💬 Nota", web_app=WebAppInfo(url=NOTE_WEBAPP_URL)),
         KeyboardButton("🔑 Credenziali", web_app=WebAppInfo(url=CREDENZIALI_WEBAPP_URL)),
         KeyboardButton("🗂️ Tabelle", web_app=WebAppInfo(url=TABELLE_WEBAPP_URL))],
        [KeyboardButton("🔐 Permessi", web_app=WebAppInfo(url=PERMESSI_WEBAPP_URL)),
         KeyboardButton("💰 Contabilità", web_app=WebAppInfo(url="https://agenda-webapp.onrender.com/contabilita.html"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def crea_e_invia_backup():
    now = datetime.datetime.now()
    filename = f"DatiBOT-{now.strftime('%d%m%y-%H')}.zip"
    zip_path = os.path.join(os.getcwd(), filename)
    files_to_include = []
    estensioni_ammesse = ('.db', '.py', '.html', '.txt', '.env')
    for item in os.listdir(os.getcwd()):
        if item.endswith(estensioni_ammesse):
            files_to_include.append(item)
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files_to_include:
                zipf.write(file)
    except Exception as e:
        return False, f"Errore creazione ZIP: {e}"
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"🤖 Backup Automatico Bot - {now.strftime('%d/%m/%Y ore %H:%M')}"
    body = f"Ciao Claudio,\n\nBackup del bot.\nData: {now.strftime('%d/%m/%Y %H:%M')}\nFile: {filename}\n\nSaluti,\nBot Agenda"
    msg.attach(MIMEText(body, 'plain'))
    try:
        with open(zip_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename={filename}")
        msg.attach(part)
    except Exception as e:
        return False, f"Errore allegato email: {e}"
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return True, filename
    except Exception as e:
        return False, f"Errore invio email: {e}"

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_IDS:
        await update.message.reply_text("⛔ Non sei autorizzato.")
        return
    await update.message.reply_text("⏳ Creazione backup in corso...")
    success, result = await asyncio.to_thread(crea_e_invia_backup)
    if success:
        await update.message.reply_text(f"✅ Backup completato!\n📦 {result}\n📧 {EMAIL_RECEIVER}")
    else:
        await update.message.reply_text(f"❌ Errore:\n{result}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot avviato!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()