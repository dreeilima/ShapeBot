from PIL import Image, ImageDraw, ImageFont
import io

def generate_progress_card(user_data):
    """
    Gera um card visual de progresso.
    user_data: dict com name, weight_start, weight_current, weight_target
    """
    # Criar canvas escuro (Dark Mode UI)
    W, H = 800, 400
    bg_color = (20, 20, 25) # Dark gray almost black
    card = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(card)
    
    # Cores
    accent_color = (0, 255, 127) # Spring Green for success/progress
    text_color = (255, 255, 255)
    secondary_text = (150, 150, 160)
    
    # Fontes (usando default se nao tiver custom, em prod usaríamos .ttf)
    # Tenta carregar uma fonte melhor se disponivel no sistema, senao default
    try:
        # Tenta fonte padrao windows ou linux
        title_font = ImageFont.truetype("arial.ttf", 40)
        subtitle_font = ImageFont.truetype("arial.ttf", 24)
        stat_font = ImageFont.truetype("arial.ttf", 60)
    except IOError:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        stat_font = ImageFont.load_default()

    # Header
    name = user_data.get('name', 'Guerreiro')
    draw.text((40, 40), f"ShapeBot // {name}", font=title_font, fill=accent_color)
    draw.text((40, 90), "Relatório de Progresso Semanal", font=subtitle_font, fill=secondary_text)
    
    # Dados
    current = user_data.get('weight_current', 0.0)
    start = user_data.get('weight_start', 0.0)
    target = user_data.get('weight_target', 0.0)
    
    # Calculo progresso
    if start != target:
        progress_pct = (start - current) / (start - target) * 100
        progress_pct = max(0, min(100, progress_pct)) # clamp 0-100
    else:
        progress_pct = 0
        
    # Stats Layout
    # Coluna 1: Atual
    draw.text((40, 160), "PESO ATUAL", font=subtitle_font, fill=secondary_text)
    draw.text((40, 190), f"{current}kg", font=stat_font, fill=text_color)
    
    # Coluna 2: Meta
    draw.text((300, 160), "META", font=subtitle_font, fill=secondary_text)
    draw.text((300, 190), f"{target}kg", font=stat_font, fill=text_color)
    
    # Barra de Progresso
    bar_x, bar_y = 40, 300
    bar_w, bar_h = 720, 30
    
    # Fundo da barra
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 50))
    
    # Preenchimento
    fill_w = int(bar_w * (progress_pct / 100))
    if fill_w > 0:
        draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=accent_color)
        
    draw.text((bar_x, bar_y - 35), f"Progresso: {progress_pct:.1f}%", font=subtitle_font, fill=accent_color)
    
    # Rodapé
    draw.text((40, 360), "Gerado por ShapeBot AI", font=ImageFont.load_default(), fill=secondary_text)

    # Output buffer
    bio = io.BytesIO()
    card.save(bio, format='PNG')
    bio.seek(0)
    return bio
