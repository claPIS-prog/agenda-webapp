import os
import logging
import zipfile
import datetime
import smtplib
import asyncio
import time
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, WebAppInfo, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "")
AUTHORIZED_IDS = [int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x.strip()]
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "claudiopiscopo@gmail.com")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN mancante")

def get_main_keyboard():
    ts = int(time.time())
    keyboard = [
        [KeyboardButton("📝 Nominativo", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/index.html?t={ts}")),
         KeyboardButton("📋 Lista", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/elencazione.html?t={ts}")),
         KeyboardButton("⏰ Scadenze", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/scadenze.html?t={ts}"))],

        [KeyboardButton("🔄 Rinnovi", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/rinnovi.html?t={ts}")),
         KeyboardButton("📋 Lista Rinnovi", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/lista_rinnovi.html?t={ts}"))],

        [KeyboardButton("💬 Nota", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/note.html?t={ts}")),
         KeyboardButton("📁 Files", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/credenziali.html?t={ts}")),
         KeyboardButton("🗂️ Tabelle", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/tabelle.html?t={ts}"))],

        [KeyboardButton("🔐 Sicurezza", web_app=WebAppInfo(url=f"https://agenda-webapp.onrender.com/sicurezza.html?t={ts}")),
         KeyboardButton("💰 Contabilità", web_app=WebAppInfo(url="https://agenda-webapp.onrender.com/contabilita.html"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def _recupera_nome_db(telegram_id: int, fallback_nome: str) -> str:
    if not DATABASE_URL:
        return fallback_nome
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(
                    NULLIF(TRIM(a.nome), ''),
                    NULLIF(TRIM(n.nominativo), ''),
                    %s
                ) AS nome_nominativo
                FROM autorizzati a
                LEFT JOIN nominativi n ON n.id = a.id
                WHERE a.telegram_id = %s
                LIMIT 1
                """,
                (fallback_nome, telegram_id),
            )
            row = cur.fetchone()
            if row and row.get("nome_nominativo"):
                return str(row["nome_nominativo"]).strip()
            return fallback_nome
    except Exception as e:
        logging.getLogger(__name__).warning(f"Impossibile leggere nome da DB per telegram_id={telegram_id}: {e}")
        return fallback_nome
    finally:
        if conn is not None:
            conn.close()

async def get_nome_nominativo(user) -> str:
    fallback = "Utente"
    if user:
        if user.full_name and user.full_name.strip():
            fallback = user.full_name.strip()
        elif user.first_name and user.first_name.strip():
            fallback = user.first_name.strip()
        elif user.username and user.username.strip():
            fallback = user.username.strip()
    if not user or not getattr(user, "id", None):
        return fallback
    return await asyncio.to_thread(_recupera_nome_db, user.id, fallback)

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
    user = update.effective_user
    user_id = user.id
    text = update.message.text
    if user_state.get(user_id) == 'waiting_password':
        if text == BOT_PASSWORD:
            user_state[user_id] = 'authenticated'
            nome_nominativo = await get_nome_nominativo(user)
            await update.message.reply_text("✅ Password corretta!", reply_markup=get_main_keyboard())
            await update.message.reply_text(f"Benvenuto {nome_nominativo}!")
            await update.message.reply_text("Seleziona un'operazione:")
        else:
            await update.message.reply_text("❌ Password errata.")
        return

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
    print("✅ Bot Telegram avviato!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()