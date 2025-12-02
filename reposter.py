# reposter.py (multi-flusso: 2 sorgenti -> liste di target separate)

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

# === CONFIGURAZIONE ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8201207494:AAGD5GuVvmhiBdwXA_IWLXo88i564jRYhl8")

# Flusso 1 (quello che già usi)
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "-1001114235602")
TARGET_CHANNELS: List[str] = os.getenv(
    "TARGET_CHANNELS",
    "@UmoreSottileOfferte,@loscrignodelleofferte,"
    "-1001165780142,@lareginadelleofferte,@ReginaDelleOfferte,"
    "-1001223224860,-1001084518839,-1003105040660"
).split(",")

# Flusso 2 (NUOVO – opzionale)
SOURCE_CHANNEL2 = os.getenv("SOURCE_CHANNEL2", "@dimezzo").strip()
TARGET_CHANNELS2_RAW = os.getenv("TARGET_CHANNELS2", "-1003161856965").strip()
TARGET_CHANNELS2: List[str] = (
    [t.strip() for t in TARGET_CHANNELS2_RAW.split(",") if t.strip()]
    if TARGET_CHANNELS2_RAW
    else []
)

REPOST_MODE = os.getenv("REPOST_MODE", "copy").lower()  # "copy" | "forward"
APPEND_FOOTER = os.getenv("APPEND_FOOTER", "").strip()  # es: "\n\n#rilancio"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("reposter")

# Timestamp di avvio: tutto ciò che è più vecchio viene ignorato
START_TIME = datetime.now(timezone.utc)

def is_source_chat(chat, source: str) -> bool:
    s = str(source).strip()
    if not s:
        return False
    if s.startswith("@"):
        return (chat.username is not None) and ("@" + chat.username).lower() == s.lower()
    try:
        return chat.id == int(s)
    except Exception:
        return False

def resolve_flow_targets(chat) -> Optional[List[str]]:
    """
    Determina a quale flusso appartiene il messaggio:
    - Se proviene da SOURCE_CHANNEL -> TARGET_CHANNELS
    - Se proviene da SOURCE_CHANNEL2 -> TARGET_CHANNELS2
    - Altrimenti None (non facciamo nulla)
    """
    # Flusso 1 (esistente)
    if is_source_chat(chat, SOURCE_CHANNEL):
        return [t.strip() for t in TARGET_CHANNELS if t.strip()]

    # Flusso 2 (nuovo) – solo se configurato
    if SOURCE_CHANNEL2 and TARGET_CHANNELS2:
        if is_source_chat(chat, SOURCE_CHANNEL2):
            return TARGET_CHANNELS2

    return None

async def repost_post_to_targets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.chat:
        return

    # Verifica da quale flusso arriva e quali target usare
    targets = resolve_flow_targets(msg.chat)
    if not targets:
        # Messaggio non proveniente dai canali sorgente configurati
        return

    # ❗ Ignora i messaggi più vecchi dell'avvio del bot
    msg_dt = (msg.date or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if msg_dt < START_TIME:
        log.debug("Ignoro messaggio antecedente all'avvio: %s < %s", msg_dt, START_TIME)
        return

    for target in targets:
        try:
            if REPOST_MODE == "forward":
                await msg.forward(chat_id=target)
            else:
                # Modalità "copy" con eventuale footer
                if msg.text:
                    text = msg.text_html or msg.text
                    if APPEND_FOOTER:
                        text += APPEND_FOOTER
                    await context.bot.send_message(
                        chat_id=target,
                        text=text,
                        parse_mode=ParseMode.HTML
                    )
                elif msg.caption and msg.effective_attachment:
                    caption = msg.caption_html or msg.caption
                    if APPEND_FOOTER:
                        caption += APPEND_FOOTER
                    await msg.copy(
                        chat_id=target,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await msg.copy(chat_id=target)

            log.info("Ripubblicato da %s su %s", msg.chat.id, target)
        except Exception as e:
            log.error("Errore pubblicando su %s: %s", target, e)

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    # ricevi solo post dei canali
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, repost_post_to_targets))
    # ❗ Scarta eventuali update pendenti all'avvio
    application.run_polling(allowed_updates=["channel_post"], drop_pending_updates=True)

if __name__ == "__main__":
    main()
