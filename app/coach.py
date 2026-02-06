import os
import warnings
# Suppress deprecation warning for now
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_persona_instruction(profile):
    """Gera a System Instruction baseada no nicho do usuário."""
    niche = profile.get('niche', 'Geral')
    preferences = profile.get('preferences', {})
    
    # Injeção de Contexto (LTM)
    context_str = ""
    if preferences:
        context_str = "\nCONTEXTO & MEMÓRIA:\n"
        for k, v in preferences.items():
            context_str += f"- {k}: {v}\n"

    # Injeção de Agenda Atual
    reminders = profile.get('reminders', [])
    schedule_str = ""
    if reminders:
        if isinstance(reminders, str):
            try: reminders = json.loads(reminders)
            except: reminders = []
        if isinstance(reminders, list):
            schedule_str = "\nAGENDA ATUAL:\n"
            for r in reminders:
                schedule_str += f"- {r.get('label')}: {r.get('time')}\n"

    # Injeção de Dieta Atual
    generated_plan = profile.get('generated_plan', {})
    if isinstance(generated_plan, str):
        try: generated_plan = json.loads(generated_plan)
        except: generated_plan = {}
    
    diet_list = generated_plan.get('diet', [])
    diet_str = ""
    if diet_list:
        diet_str = "\nDIETA ATUAL:\n"
        for meal in diet_list:
            foods = ", ".join(meal.get('foods', []))
            diet_str += f"- {meal.get('meal')}: {foods}\n"

    # Injeção de Treino Atual
    workout = generated_plan.get('workout', {})
    workout_str = ""
    if workout:
        workout_str = f"\nTREINO ATUAL ({workout.get('split', 'Geral')}):\n"
        for day in workout.get('days', []):
            exercises = ", ".join(day.get('exercises', []))
            workout_str += f"- {day.get('day')}: {exercises}\n"

    base_instruction = f"""
    Você é o ShapeBot, um Coach de Alta Performance e Nutricionista.
    
    DADOS DO CLIENTE:
    Nome: {profile.get('name')}
    Altura: {profile.get('height')}m
    Peso Atual: {profile.get('weight_current')}kg
    Meta: {profile.get('weight_target')}kg
    Nível Atividade: {profile.get('activity_level')}
    {context_str}
    {schedule_str}
    {diet_str}
    {workout_str}
    
    DIRETRIZES TÉCNICAS:
    - Se receber uma imagem de comida, analise calorias e macros estimados com precisão.
    - Se receber áudio, transcreva mentalmente e responda direto ao ponto.
    
    COMANDOS DE SISTEMA (IMPORTANTE):
    
    1. ALTERAÇÃO DE HORÁRIO:
       - Se o usuário pedir para mudar horário, output:
         [[UPDATE_SCHEDULE: {{"label": "Nome Exato", "time": "HH:MM"}}]]
         
    2. ALTERAÇÃO DE DIETA (Troca de Alimentos):
       - Se o usuário pedir para trocar um alimento (ex: "Troca frango por picanha"), você DEVE:
         a) Calcular os macros do alimento original.
         b) Calcular quanto do NOVO alimento é necessário para bater os mesmos macros (principalmente calorias e proteínas).
         c) Se for uma troca muito ruim (ex: Salada por Pizza), EXPLIQUE o impacto negativo e sugira moderação, mas se for viável, CALCULE a porção correta.
         d) Output do token com a refeição ATUALIZADA (lista completa de alimentos daquela refeição):
         [[UPDATE_DIET: {{"meal": "Nome da Refeição (ex: Almoço)", "foods": ["Novo Alimento 1 (quantidade calculada)", "Alimento 2 mantido"]}}]]

    3. ALTERAÇÃO DE TREINO:
       - Se o usuário pedir para trocar exercício (ex: "Troca Supino por Flexão"), output com o dia ATUALIZADO:
         [[UPDATE_WORKOUT: {{"day": "Dia da Semana (ex: Segunda)", "exercises": ["Novo Exercício 1", "Exercício 2 mantido"]}}]]
         
    4. REGISTRO DE ÁGUA:
       - Se o usuário disser que bebeu água (ex: "Tomei 300ml"), output apenas o número (inteiro):
         [[LOG_WATER: 300]]
         
    5. ATUALIZAÇÃO DE PESO:
       - Se o usuário atualizar o peso (ex: "Estou com 75kg"), output o número (float):
         [[UPDATE_WEIGHT: 75.0]]
    """
    
    if niche == 'Programador':
        return base_instruction + """
        PERSONALIDADE (MODO DEV):
        - Aja como um Tech Lead Sênior da Saúde.
        - Use analogias de código: 'bug no shape', 'deploy de massa magra', 'refatorar a dieta', 'garbage collection' (detox).
        - Trate o corpo como um sistema em produção que precisa de alta disponibilidade.
        - Seja prático, lógico e direto.
        """
    elif niche == 'Executivo':
        return base_instruction + """
        PERSONALIDADE (MODO EXECUTIVO):
        - Aja como um Consultor de Alta Performance.
        - Foco em ROI (Retorno sobre Investimento) de energia e tempo.
        - Use termos como 'asset', 'liability', 'otimização de recursos', 'bottom line'.
        - Seja extremamente polido, eficiente e focado em resultados rápidos.
        """
    else: # Geral
        return base_instruction + """
        PERSONALIDADE (MODO COACH):
        - Seja motivador, energético e acolhedor.
        - Use emojis e linguagem acessível.
        - Foco em bem-estar e consistência.
        - Aja como aquele personal trainer gente boa.
        """

def think_as_coach(user_input, user_profile, media_data=None, media_type=None):
    """
    Processa entrada texto ou multimodal.
    media_data: Bytes (imagem ou audio) ou PIL Image
    media_type: Mime type str (ex: 'image/jpeg', 'audio/mp3')
    """
    try:
        if not user_profile:
            user_profile = {"name": "Visitante", "niche": "Geral"}
            
        system_instruction = get_persona_instruction(user_profile)
        
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash-preview-09-2025",
            system_instruction=system_instruction
        )
        
        content_parts = []
        if user_input:
            content_parts.append(user_input)
            
        if media_data:
            if isinstance(media_data, Image.Image):
                content_parts.append(media_data)
            else:
                # Assuming raw bytes for manual blob construction if needed, 
                # but Gemini Python SDK usually takes a dict or special object for Blob.
                # Simplificando: Assumimos que media_data virá como PIL Image para fotos
                # Para Audio, talvez precisemos de ajuste. 
                # Vamos focar na conversão prévia no main.py ou usar a API de File se for grande.
                # Para MVP rápido de Voz: Mandar o blob.
                content_parts.append({
                    "mime_type": media_type or "audio/mp3",
                    "data": media_data
                })

        response = model.generate_content(content_parts)
        return response.text
    except Exception as e:
        return f"Erro de processamento no neural core: {e}"

import json

def get_gemini_response(user_input):
    return think_as_coach(user_input, None)

def generate_full_plan(profile):
    """
    Gera um plano completo (Dieta, Treino, Agenda) em JSON.
    """
    prompt = f"""
    Crie um plano de transformação completo para este perfil, no formato JSON estrito.
    
    PERFIL:
    - Nome: {profile.get('name')}
    - Altura: {profile.get('height')}
    - Peso: {profile.get('weight_current')} (Meta: {profile.get('weight_target')})
    - Nível: {profile.get('activity_level')}
    - Nicho: {profile.get('niche')}
    - Preferências: {profile.get('preferences')}

    O JSON deve ter exatamente estas chaves:
    {{
        "diet": [
            {{"meal": "Café da Manhã", "time": "08:00", "foods": ["...", "..."], "calories": 500}},
            ...
        ],
        "workout": {{
            "split": "ABC ou Fullbody...",
            "days": [
                {{"day": "Segunda", "focus": "Peito e Tríceps", "exercises": ["...", "..."]}}
            ]
        }},
        "schedule": [
            {{"label": "Café da Manhã", "time": "08:00", "message": "Hora de comer! Foco na proteína."}},
            {{"label": "Água 1", "time": "10:00", "message": "Hidratação! 500ml pra dentro."}},
            {{"label": "Treino", "time": "18:00", "message": "Bora esmagar! Dia de..."}}
        ]
    }}
    
    Responda APENAS o JSON, sem markdown (```json).
    """

    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash-preview-09-2025")
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Erro ao gerar plano: {e}")
        return None
