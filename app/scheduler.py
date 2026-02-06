from telegram.ext import ContextTypes
import datetime
import json
from .database import get_all_users, get_daily_water_total

async def check_hydration(context: ContextTypes.DEFAULT_TYPE):
    """
    Roda as 14:00 diariamente.
    Verifica se o usuário bebeu pelo menos 50% da meta de água.
    Meta = Peso * 35ml
    """
    users = get_all_users()
    for user in users:
        try:
            user_id = user['telegram_id']
            weight = user.get('weight')
            
            if not weight: continue # Sem peso, sem meta
            
            target = weight * 35 # ML
            half_target = target / 2
            
            current = get_daily_water_total(user_id)
            
            if current < half_target:
                msg = (
                    f"⚠️ *Alerta de Hidratação*\n\n"
                    f"Já passamos da metade do dia e você bebeu apenas *{int(current)}ml*.\n"
                    f"Sua meta diária é *{int(target)}ml*.\n\n"
                    f"💡 Beba 500ml agora para compensar!"
                )
                await context.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
        except Exception as e:
            print(f"Erro no check de hidratação para {user.get('name')}: {e}")

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """
    Job que roda a cada minuto (Ticker).
    Verifica se algum usuário tem lembrete para o horário atual.
    """
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M")
    
    # Busca usuários e seus lembretes
    users = get_all_users()
    
    for user in users:
        reminders = user.get('reminders', [])
        # Reminders é uma string JSON se vier do banco puro, ou lista se o driver converter?
        # O psycopg2 + JSONB costuma retornar lista/dict python direto.
        # Mas por via das dúvidas, vamos garantir.
        if isinstance(reminders, str):
            try:
                reminders = json.loads(reminders)
            except:
                reminders = []
        
        if not reminders:
            continue
            
        chat_id = user['telegram_id']
        name = user['name']
        
        for item in reminders:
            # item espera-se: {"time": "08:00", "label": "Café", "message": "..."}
            if item.get('time') == current_time:
                msg = f"⏰ **{item.get('label', 'Lembrete')}:**\n\n{item.get('message', 'Hora de agir!')}"
                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg)
                    # Opcional: Logar que enviou
                except Exception as e:
                    print(f"Falha ao enviar msg para {name} ({chat_id}): {e}")

def setup_notifications(job_queue):
    # Remove jobs antigos se houver (opcional, mas bom pra reload)
    # job_queue.scheduler.remove_all_jobs()
    
    # Adiciona o Ticker de Minuto
    job_queue.run_repeating(
        check_reminders,
        interval=60,
        first=10, # Começa em 10s
        name="dynamic_reminders_ticker"
    )
    
    # Adiciona Check de Hidratação (14:00)
    job_queue.run_daily(
        check_hydration,
        time=datetime.time(hour=14, minute=0),
        days=(0, 1, 2, 3, 4, 5, 6), # Todos os dias
        name="hydration_check"
    )
