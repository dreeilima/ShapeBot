import psycopg2
import os
from contextlib import contextmanager
import json

@contextmanager
def get_connection():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Inicializa as tabelas do sistema SaaS."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Tabela de Usuários (Multi-tenant)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        telegram_id BIGINT PRIMARY KEY,
                        name VARCHAR(255),
                        height FLOAT,
                        weight_start FLOAT,
                        weight_current FLOAT,
                        weight_target FLOAT,
                        activity_level VARCHAR(50),
                        niche VARCHAR(50),
                        preferences JSONB DEFAULT '{}',
                        generated_plan JSONB DEFAULT '{}',
                        reminders JSONB DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Migração: Garantir colunas novas em tabelas existentes
                try:
                    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS generated_plan JSONB DEFAULT '{}';")
                    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reminders JSONB DEFAULT '[]';")
                except Exception as e:
                    print(f"Aviso migração: {e}")
                
                # Logs de Consumo vinculados ao Usuário
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_logs (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(telegram_id),
                        log_type VARCHAR(20),
                        value FLOAT,
                        meta_data JSONB,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                print("DB: Tabelas 'users' e 'user_logs' verificadas/criadas.")
    except Exception as e:
        print(f"Erro ao inicializar DB: {e}")

def create_or_update_user(telegram_id, data):
    """Cria ou atualiza um usuário no banco."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (telegram_id, name, height, weight_start, weight_current, weight_target, activity_level, niche, preferences)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (telegram_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        height = EXCLUDED.height,
                        weight_current = EXCLUDED.weight_current,
                        weight_target = EXCLUDED.weight_target,
                        activity_level = EXCLUDED.activity_level,
                        niche = EXCLUDED.niche,
                        preferences = COALESCE(users.preferences, '{}') || EXCLUDED.preferences;
                """, (
                    telegram_id,
                    data.get('name'),
                    data.get('height'),
                    data.get('weight'), # Initial weight
                    data.get('weight'),
                    data.get('target_weight'),
                    data.get('activity_level'),
                    data.get('niche'),
                    json.dumps(data.get('preferences', {}))
                ))
                conn.commit()
                return True
    except Exception as e:
        print(f"Erro ao salvar usuário {telegram_id}: {e}")
        return False

def get_user_profile(telegram_id):
    """Busca o perfil completo do usuário."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                columns = [desc[0] for desc in cur.description]
                row = cur.fetchone()
                if row:
                    return dict(zip(columns, row))
                return None
    except Exception as e:
        print(f"Erro ao buscar usuário {telegram_id}: {e}")
        return None

def save_log(telegram_id, log_type, value, description="", meta_data=None):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_logs (user_id, log_type, value, description, meta_data) 
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (telegram_id, log_type, value, description, json.dumps(meta_data) if meta_data else None)
                )
                conn.commit()
    except Exception as e:
        print(f"Erro ao salvar log: {e}")

def update_user_plan(user_id, plan_data):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET generated_plan = %s WHERE telegram_id = %s",
                    (json.dumps(plan_data), user_id)
                )
                conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar plano: {e}")
        return False

def get_user_plan(user_id):
    profile = get_user_profile(user_id)
    return profile.get('generated_plan') if profile else {}

def update_reminders(user_id, reminders_list):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET reminders = %s WHERE telegram_id = %s",
                    (json.dumps(reminders_list), user_id)
                )
                conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar lembretes: {e}")
        return False

def get_reminders(user_id):
    profile = get_user_profile(user_id)
    return profile.get('reminders', []) if profile else []

def delete_user_data(user_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_logs WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM users WHERE telegram_id = %s", (user_id,))
                conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao deletar usuário: {e}")
        return False

def get_all_users():
    """Retorna lista de todos os usuários para o scheduler."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT telegram_id, name, niche, reminders, weight_current FROM users")
                rows = cur.fetchall()
                # Retorna lista de dicts
                return [{"telegram_id": r[0], "name": r[1], "niche": r[2], "reminders": r[3], "weight": r[4]} for r in rows]
    except Exception as e:
        print(f"Erro ao buscar todos usuários: {e}")
        return []

def get_daily_water_total(user_id):
    """Retorna o total de água (ml) consumido hoje pelo usuário."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT SUM(value) 
                    FROM user_logs 
                    WHERE user_id = %s 
                      AND log_type = 'WATER' 
                      AND created_at::date = CURRENT_DATE
                """, (user_id,))
                result = cur.fetchone()[0]
                return result if result else 0.0
    except Exception as e:
        print(f"Erro ao calcular hidratação: {e}")
        return 0.0

def update_user_weight(user_id, new_weight):
    """Atualiza o peso atual e salva log."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET weight_current = %s WHERE telegram_id = %s", (new_weight, user_id))
                # Log do peso para gráfico
                cur.execute("""
                    INSERT INTO user_logs (user_id, log_type, value, description)
                    VALUES (%s, 'WEIGHT', %s, 'Atualização Manual')
                """, (user_id, new_weight))
                conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar peso: {e}")
        return False

def get_user_history(user_id):
    """
    Retorna histórico para gráficos (Peso e Água).
    Formato: {
        "dates": [...],
        "weight": [...],
        "water": [...]
    }
    """
    try:
        data = {"dates": [], "weight": [], "water": []}
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Histórico de Peso (Últimos 30 registros)
                cur.execute("""
                    SELECT created_at::date, value 
                    FROM user_logs 
                    WHERE user_id = %s AND log_type = 'WEIGHT'
                    ORDER BY created_at ASC
                """, (user_id,))
                weight_rows = cur.fetchall()
                
                # 2. Histórico de Água (Soma diária, últimos 7 dias)
                cur.execute("""
                    SELECT created_at::date, SUM(value)
                    FROM user_logs
                    WHERE user_id = %s AND log_type = 'WATER'
                    GROUP BY created_at::date
                    ORDER BY created_at::date ASC
                    LIMIT 7
                """, (user_id,))
                water_rows = cur.fetchall()

                # Processar Peso (simples)
                for date, val in weight_rows:
                    d_str = date.strftime("%d/%m")
                    if d_str not in data["dates"]:
                        data["dates"].append(d_str)
                    data["weight"].append(val)
                
                # Processar Água (mapa de datas)
                water_map = {row[0].strftime("%d/%m"): row[1] for row in water_rows}
                
                # 3. Stats do Cabeçalho (Peso Atual, Meta, Água Hoje)
                # Reutiliza queries ou chama funções helpers se performance não for crítica
                # Como já estamos com conexão aberta, melhor query direta
                cur.execute("SELECT weight_current, weight_target FROM users WHERE telegram_id = %s", (user_id,))
                user_row = cur.fetchone()
                current_weight = user_row[0] if user_row else 0
                target_weight = user_row[1] if user_row else 0
                
                cur.execute("""
                    SELECT SUM(value) FROM user_logs 
                    WHERE user_id = %s AND log_type = 'WATER' AND created_at::date = CURRENT_DATE
                """, (user_id,))
                water_res = cur.fetchone()[0]
                water_today = water_res if water_res else 0

                return {
                    "weight_labels": [r[0].strftime("%d/%m") for r in weight_rows],
                    "weight_values": [r[1] for r in weight_rows],
                    "water_labels": [r[0].strftime("%d/%m") for r in water_rows],
                    "water_values": [r[1] for r in water_rows],
                    "stats": {
                        "current_weight": current_weight,
                        "target_weight": target_weight,
                        "water_today": water_today
                    }
                }

    except Exception as e:
        print(f"Erro ao gerar histórico: {e}")
        return {}
