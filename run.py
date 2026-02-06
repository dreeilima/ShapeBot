import os
import logging
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)

from app.database import init_db
from app.scheduler import setup_notifications
from app.handlers import (
    start, cancel, handle_message, handle_photo, handle_voice, handle_status, show_help,
    get_name, get_height, get_weight, get_target, get_activity, get_niche, get_custom_niche,
    cmd_reset, reset_confirm_handler, handle_water_callback,
    NOME, ALTURA, PESO, META, ATIVIDADE, NICHE, CUSTOM_NICHE
)

# Configuração de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

async def error_handler(update, context):
    logging.error(f"Update {update} caused error {context.error}")

import asyncio
import uvicorn
from app.api import app as api_app

async def main():
    # Inicializa DB
    init_db()
    
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("ERRO: TELEGRAM_TOKEN ausente.")
        return

    # Build Bot Application
    application = Application.builder().token(token).build()
    
    # Conversation Handler para Onboarding
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ALTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            PESO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            META: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_target)],
            ATIVIDADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity)],
            NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_niche)],
            CUSTOM_NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_custom_niche)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Registra Handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("status", handle_status))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("reset", cmd_reset))
    application.add_handler(CallbackQueryHandler(reset_confirm_handler, pattern='^(confirm_reset|cancel_reset)$'))
    application.add_handler(CallbackQueryHandler(handle_water_callback, pattern='^water_'))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)

    # Configura Scheduler Global
    setup_notifications(application.job_queue)

    print("ShapeBot Enterprise (Hybrid Server) iniciando... 🚀")
    
    # Porta dinâmica para Koyeb/Cloud
    port = int(os.getenv("PORT", 8001))
    print(f"API Dashboard rodando em: http://0.0.0.0:{port}")

    # Start Bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Start API Server
    config = uvicorn.Config(api_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        # Run Server (blocks until CTRL+C)
        await server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup Bot
        print("Parando Bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    # Fix for Windows Asyncio Loop
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
