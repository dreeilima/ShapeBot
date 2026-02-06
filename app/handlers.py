import logging
import os
import io
import json
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from PIL import Image

# Relative imports
from .coach import think_as_coach, generate_full_plan
from .database import (
    save_log, create_or_update_user, get_user_profile, 
    update_user_plan, update_reminders, get_user_plan, 
    get_reminders, delete_user_data, get_daily_water_total
)
from .graphics import generate_progress_card

# States for Onboarding
NOME, ALTURA, PESO, META, ATIVIDADE, NICHE, CUSTOM_NICHE = range(7)

def get_main_menu_keyboard():
    keyboard = [
        ['🍽️ Minha Dieta', '🏋️ Meu Treino'],
        ['💧 Hidratação', '📅 Meus Horários'],
        ['📊 Status', '💡 Comandos'],
        ['👤 Perfil']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if profile:
        await update.message.reply_text(
            f"E aí, {profile['name']}! 🚀\n"
            f"ShapeBot online. Modo: {profile['niche']}.\n",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "👋 Fala! Eu sou o ShapeBot.\n"
            "Vi que você é novo por aqui. Pra eu montar seu treino e dieta perfeitos, preciso calibrar meu sistema com seus dados.\n\n"
            "Vamos lá! Primeiro: *Como você quer ser chamado?*",
            parse_mode='Markdown'
        )
        return NOME

# --- ONBOARDING STEPS ---
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"Boa, {context.user_data['name']}! Qual a sua *altura*? (ex: 1.75)", parse_mode='Markdown')
    return ALTURA

async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.replace(',', '.'))
        context.user_data['height'] = height
        await update.message.reply_text("Show. E qual seu *peso atual* (kg)? (ex: 80.5)", parse_mode='Markdown')
        return PESO
    except ValueError:
        await update.message.reply_text("Ops! Digite apenas o número. Ex: 1.75")
        return ALTURA

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(',', '.'))
        context.user_data['weight'] = weight
        await update.message.reply_text("Peso calibrado. Qual sua *meta de peso* (kg)?", parse_mode='Markdown')
        return META
    except ValueError:
        await update.message.reply_text("Número inválido. Tente algo como 80.5")
        return PESO

async def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target = float(update.message.text.replace(',', '.'))
        context.user_data['target_weight'] = target
        
        reply_keyboard = [
            ['Sedentário (0x)', 'Leve (1-2x)'],
            ['Moderado (3-4x)', 'Intenso (5-6x)'],
            ['Atleta (7x+)']
        ]
        await update.message.reply_text(
            "Beleza. Qual seu nível de atividade física hoje? (Seja sincero!)",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return ATIVIDADE
    except ValueError:
        await update.message.reply_text("Digite só o número da meta.")
        return META

async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['activity_level'] = update.message.text
    
    reply_keyboard = [
        ['Programador 💻', 'Executivo 💼'],
        ['Geral ⚡', 'Personalizar 📝']
    ]
    await update.message.reply_text(
        "Última config! Com qual perfil você se identifica?\n"
        "(Isso muda minha personalidade e como eu falo com você!)",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return NICHE

async def get_niche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text
    if "Personalizar" in user_choice:
        await update.message.reply_text(
            "Top! 🛠️ Descreva em poucas palavras como você quer que eu aja.\n"
            "Ex: 'Seja um sargento bravo', 'Fale como o Yoda', 'Seja puramente científico'."
        )
        return CUSTOM_NICHE

    niche_map = {
        'Programador 💻': 'Programador',
        'Executivo 💼': 'Executivo',
        'Geral ⚡': 'Geral'
    }
    context.user_data['niche'] = niche_map.get(user_choice, 'Geral')
    return await finish_onboarding(update, context)

async def get_custom_niche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_description = update.message.text
    context.user_data['niche'] = 'Custom'     
    preferences = context.user_data.setdefault('preferences', {})
    preferences['personalidade_custom'] = custom_description
    return await finish_onboarding(update, context)

async def finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 1. Salvar Perfil Básico
    success = create_or_update_user(user_id, context.user_data)
    
    if success:
        await update.message.reply_text(
            "✅ Perfil Salvo! \n\n"
            "🧠 *O Cérebro Neural está processando seu plano...*\n"
            "(Criando dieta, treino e horários personalizados... aguarde uns segundos)\n\n"
            "💡 *Dica:* Depois você pode falar coisas como:\n"
            "_'Mude meu café para 09:00'_ ou _'Troque pão por tapioca'_ que eu entendo!",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # 2. Gerar Plano Completo (AI)
        profile = context.user_data
        full_plan = generate_full_plan(profile)
        
        if full_plan:
            # 3. Salvar Plano e Lembretes no DB
            update_user_plan(user_id, full_plan)
            
            reminders = full_plan.get('schedule', [])
            update_reminders(user_id, reminders)
            
            await update.message.reply_text(
                "🔥 *PLANO PRONTO!* 🔥\n\n"
                "Seu protocolo exclusivo foi carregado.\n"
                "Use o Menu abaixo para ver os detalhes.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "Tive um erro ao gerar o plano detalhado, mas seu perfil está salvo!\n"
                "Tente novamente mais tarde.",
                reply_markup=get_main_menu_keyboard()
            )
            
    else:
        await update.message.reply_text("Erro crítico ao salvar perfil. Tente /start.", reply_markup=ReplyKeyboardRemove())
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- MAIN MENU HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    profile = get_user_profile(user_id)
    if not profile:
        await update.message.reply_text("Eita, não te achei no sistema. Dá um /start pra gente configurar seu perfil!")
        return

    # Menu Routing
    if user_text == '🍽️ Minha Dieta':
        await show_diet(update, context, user_id)
    elif user_text == '🏋️ Meu Treino':
        await show_workout(update, context, user_id)
    elif user_text == '📅 Meus Horários':
        await show_schedule(update, context, user_id)
    elif user_text == '💧 Hidratação':
        await log_water_flow(update, context, user_id)
    elif user_text == '📊 Status':
        await handle_status(update, context)
    elif user_text == '💡 Comandos':
        await show_help(update, context)
    elif user_text == '👤 Perfil':
        await show_profile(update, context, profile)
    else:
        # Chat Normal com Coach
        if user_text:
            response = think_as_coach(user_text, profile)
            save_log(user_id, "TALK", 0, "Conversa com Coach")

            # Check for schedule updates (NL Smart Interaction)
            match = re.search(r'\[\[UPDATE_SCHEDULE: (.*?)\]\]', response)
            if match:
                try:
                    cmd_data = json.loads(match.group(1))
                    label = cmd_data.get('label')
                    new_time = cmd_data.get('time')
                    
                    reminders = get_reminders(user_id)
                    # Convert raw string to list if needed
                    if isinstance(reminders, str): reminders = json.loads(reminders)
                    
                    updated = False
                    for r in reminders:
                        # Fuzzy match simples: se o label contiver a palavra
                        if label.lower() in r.get('label', '').lower() or r.get('label', '').lower() in label.lower():
                            r['time'] = new_time
                            updated = True
                            label = r.get('label') # Use original label for msg
                            break
                    
                    if updated:
                        update_reminders(user_id, reminders)
                        confirmation = f"\n✅ **Agenda Atualizada:** {label} ➡️ {new_time}"
                        response = response.replace(match.group(0), confirmation)
                    else:
                        response = response.replace(match.group(0), "")
                        
                except Exception as e:
                    print(f"Error parsing update schedule: {e}")
                    response = response.replace(match.group(0), "")

            # Check for DIET updates
            match_diet = re.search(r'\[\[UPDATE_DIET: (.*?)\]\]', response)
            if match_diet:
                try:
                    cmd_data = json.loads(match_diet.group(1))
                    target_meal = cmd_data.get('meal') # Ex: "Café da Manhã"
                    new_foods = cmd_data.get('foods')  # List of strings
                    
                    plan = get_user_plan(user_id)
                    diet = plan.get('diet', [])
                    
                    updated = False
                    for meal in diet:
                        # Fuzzy match no nome da refeição
                        if target_meal.lower() in meal.get('meal', '').lower() or meal.get('meal', '').lower() in target_meal.lower():
                            meal['foods'] = new_foods
                            updated = True
                            target_meal = meal.get('meal')
                            break
                    
                    if updated:
                        update_user_plan(user_id, plan)
                        foods_str = ", ".join(new_foods)
                        confirmation = f"\n🥗 **Dieta Atualizada:** {target_meal} ➡️ {foods_str}"
                        response = response.replace(match_diet.group(0), confirmation)
                    else:
                        response = response.replace(match_diet.group(0), "")

                except Exception as e:
                    print(f"Error parsing update diet: {e}")
                    response = response.replace(match_diet.group(0), "")

            # Check for WORKOUT updates
            match_workout = re.search(r'\[\[UPDATE_WORKOUT: (.*?)\]\]', response)
            if match_workout:
                try:
                    cmd_data = json.loads(match_workout.group(1))
                    target_day = cmd_data.get('day') # Ex: "Segunda"
                    new_exercises = cmd_data.get('exercises')  # List of strings
                    
                    plan = get_user_plan(user_id)
                    workout = plan.get('workout', {})
                    days = workout.get('days', [])
                    
                    updated = False
                    for day in days:
                        # Fuzzy match no nome do dia
                        if target_day.lower() in day.get('day', '').lower() or day.get('day', '').lower() in target_day.lower():
                            day['exercises'] = new_exercises
                            updated = True
                            target_day = day.get('day')
                            break
                    
                    if updated:
                        update_user_plan(user_id, plan)
                        ex_str = ", ".join(new_exercises)
                        confirmation = f"\n🏋️ *Treino Atualizado:* {target_day} ➡️ {ex_str}"
                        response = response.replace(match_workout.group(0), confirmation)
                    else:
                        response = response.replace(match_workout.group(0), "")

                except Exception as e:
                    print(f"Error parsing update workout: {e}")
                    response = response.replace(match_workout.group(0), "")

            # Check for WATER logging (NLP)
            # [[LOG_WATER: 300]]
            match_water = re.search(r'\[\[LOG_WATER: (\d+)\]\]', response)
            if match_water:
                try:
                    amount = int(match_water.group(1))
                    save_log(user_id, "WATER", amount, "NLP")
                    total = get_daily_water_total(user_id)
                    confirmation = f"\n💧 *Hidratação:* +{amount}ml (Total: {int(total)}ml)"
                    response = response.replace(match_water.group(0), confirmation)
                except Exception as e:
                    print(f"Error parsing log water: {e}")
                    response = response.replace(match_water.group(0), "")

            # Check for WEIGHT updates (NLP)
            # [[UPDATE_WEIGHT: 75.5]]
            match_weight = re.search(r'\[\[UPDATE_WEIGHT: ([\d\.]+)\]\]', response)
            if match_weight:
                try:
                    new_weight = float(match_weight.group(1))
                    from .database import update_user_weight # Lazy import to avoid cycle if needed or just standard
                    update_user_weight(user_id, new_weight)
                    confirmation = f"\n⚖️ *Peso Atualizado:* {new_weight}kg"
                    response = response.replace(match_weight.group(0), confirmation)
                except Exception as e:
                    print(f"Error parsing weight update: {e}")
                    response = response.replace(match_weight.group(0), "")
            
            # Markdown Fix for Response
            response = response.replace("**", "*")
            
            await update.message.reply_text(response, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')

async def show_diet(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    plan = get_user_plan(user_id)
    diet = plan.get('diet', []) if plan else []
    
    if not diet:
        await update.message.reply_text("Sua dieta ainda não foi gerada. Tente recriar o perfil.")
        return

    msg = "🥗 *Protocolo Alimentar*\n\n"
    for meal in diet:
        foods = ", ".join(meal.get('foods', []))
        msg += f"🕒 *{meal.get('time', '??:??')} - {meal.get('meal')}*\n"
        msg += f"   _{foods}_\n   (~{meal.get('calories', 0)} kcal)\n\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_workout(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    plan = get_user_plan(user_id)
    workout = plan.get('workout', {}) if plan else {}
    
    if not workout:
        await update.message.reply_text("Treino não encontrado.")
        return

    msg = f"🏋️ *Protocolo de Treino* ({workout.get('split', 'Geral')})\n\n"
    for day in workout.get('days', []):
        msg += f"📅 *{day.get('day')}* - {day.get('focus')}\n"
        for ex in day.get('exercises', []):
            msg += f"   • {ex}\n"
        msg += "\n"
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    reminders = get_reminders(user_id)
    if not reminders:
        await update.message.reply_text("Sem lembretes configurados.")
        return

    msg = "⏰ *Sua Agenda Diária*\n\n"
    # Ordenar por horário
    sorted_reminders = sorted(reminders, key=lambda x: x.get('time', '00:00'))
    
    for r in sorted_reminders:
        msg += f"• *{r.get('time')}* - {r.get('label')}\n"
    
    msg += "\n_Eu te avisarei nestes horários!_"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def log_water_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    keyboard = [
        [InlineKeyboardButton("💧 250ml", callback_data='water_250'), InlineKeyboardButton("🥤 500ml", callback_data='water_500')],
        [InlineKeyboardButton("📝 Personalizar", callback_data='water_custom')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Busca total do dia
    total = get_daily_water_total(user_id)
    
    await update.message.reply_text(
        f"💧 *Painel de Hidratação*\n"
        f"Total hoje: *{int(total)}ml*\n"
        f"Escolha uma opção:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_water_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    amount = 0
    if query.data == 'water_250': amount = 250
    elif query.data == 'water_500': amount = 500
    elif query.data == 'water_custom':
        await query.edit_message_text("Digite a quantidade em ml (ex: 300):")
        return # Future: Handle next message as number
        
    if amount > 0:
        save_log(user_id, "WATER", amount, "Menu")
        total = get_daily_water_total(user_id)
        await query.edit_message_text(f"✅ *+{amount}ml* registrado!\n🌊 Total hoje: *{int(total)}ml*", parse_mode='Markdown')

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, profile):
    msg = (
        f"👤 *Perfil de Atleta*\n"
        f"Nome: {profile['name']}\n"
        f"Nicho: {profile['niche']}\n"
        f"Peso: {profile['weight_current']}kg (Meta: {profile['weight_target']}kg)\n\n"
        "Para resetar tudo, digite /reset."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💡 *Central de Comandos*\n\n"
        "Além dos botões, você pode conversar comigo! Tente estas frases:\n\n"
        "🗓️ *Agenda*\n"
        "• _\"Mude meu treino para 19:00\"_\n"
        "• _\"Crie um lembrete de Creatina às 08:00\"_\n\n"
        "🥗 *Dieta*\n"
        "• _\"Troque pão por tapioca no café\"_\n"
        "• _\"Quero comer macarrão no almoço\"_\n"
        "_(Eu calculo as quantidades pra você!)_\n\n"
        "🏋️ *Treino*\n"
        "• _\"Troque Supino por Flexão no treino A\"_\n"
        "• _\"Hoje quero treinar Costas\"_\n\n"
        "💧 *Hidratação*\n"
        "• _\"Tomei 300ml de água\"_\n"
        "• _\"Registrar 1 copo grande\"_\n\n"
        "⚖️ *Progresso*\n"
        "• _\"Estou pesando 75.5kg\"_\n"
        "• _\"Atualizar peso para 80kg\"_\n\n"
        "Experimente falar do seu jeito, eu entendo!"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- MEDIA HANDLERS ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    if not profile: return 

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    image = Image.open(io.BytesIO(photo_bytes))
    user_text = update.message.caption or "Analise esta imagem."
    
    response = think_as_coach(user_text, profile, media_data=image)
    save_log(user_id, "VISION", 0, "Photo Analysis")
    # Fix markdown
    response = response.replace("**", "*")
    await update.message.reply_text(response, parse_mode='Markdown')

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    if not profile: return 

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    voice_file = await update.message.voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()
    
    response = think_as_coach("Audio enviado.", profile, media_data=voice_bytes, media_type="audio/mp3")
    save_log(user_id, "VOICE", 0, "Voice Interaction")
    # Fix markdown
    response = response.replace("**", "*")
    await update.message.reply_text(response, parse_mode='Markdown')

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    if not profile: return 

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    image_bio = generate_progress_card(profile)
    
    # Dashboard Button
    base_url = os.getenv("DASHBOARD_URL", "http://127.0.0.1:8001").rstrip("/")
    keyboard = [[InlineKeyboardButton("📈 Abrir Dashboard", url=f"{base_url}/?user_id={user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(photo=image_bio, caption="📊 *Seu Progresso*", reply_markup=reply_markup, parse_mode='Markdown')

# --- RESET FLOW ---
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ SIM, Apagar Tudo", callback_data='confirm_reset')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancel_reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚠️ *ZONA DE PERIGO* ⚠️\n\n"
        "Você tem certeza que deseja deletar todo o seu perfil, histórico e planos?\n"
        "Essa ação é irreversível.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def reset_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'confirm_reset':
        user_id = query.from_user.id
        delete_user_data(user_id)
        await query.edit_message_text("🗑️ *Perfil Deletado.*\nDigite /start para começar do zero.", parse_mode='Markdown')
    else:
        await query.edit_message_text("Ufa! Operação cancelada. Seus dados estão salvos.")
