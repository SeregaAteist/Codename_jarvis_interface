"""Начальные данные конфигурации (RF-12): источники, промпты, Drive-папки.

Засеваются один раз при init_db(), если таблицы пусты. Дальше управление —
кнопками в TG (Настройки), правки в БД переживают деплой.
"""
from __future__ import annotations

SOURCES = [
    # (domain, name, url, type, selector, track)
    ("ses", "Ecotown", "https://ecotown.com.ua/feed/", "rss", None, "all"),
    ("ses", "Kosatka Media", "https://kosatka.media/rss", "rss", None, "all"),
    ("ses", "Avenston Blog", "https://avenston.com/articles/", "web", "article h2 a", "engineers"),
    ("ses", "PV Magazine", "https://www.pv-magazine.com/feed/", "rss", None, "engineers"),
    ("energy", "НКРЕКП Новини", "https://www.nerc.gov.ua/news", "web", ".news-item a", "engineers"),
    ("energy", "Energo UA", "https://enkorr.ua/rss", "rss", None, "all"),
    ("energy", "ExPro Electricity", "https://expro.com.ua/rss", "rss", None, "engineers"),
    ("sales", "HubSpot Sales Blog", "https://blog.hubspot.com/sales/rss.xml", "rss", None, "sales"),
    ("sales", "Close Blog", "https://www.close.com/blog/rss.xml", "rss", None, "sales"),
]

DRIVE_FOLDERS = [
    # (key, folder_id, title)
    ("moodle_root",    "1AsasJyrCVSsISI6q0kRI-oROj_imYdt-", "Moodle корень"),
    ("course_ses",     "1xSSn_XWVJPCsgRXKkyZ8QPdaJUHPoADF", "Курс Менеджер СЕС"),
    ("section_admin",  "1-mR-fTWH5UBqpBMzVv8rkLaz6g_Jdy3Y", "_АДМИН"),
    ("section_start",  "1k65M1KPNZvmdiZ95WaeWYTRze2eck9VM", "00. СТАРТ"),
    ("section_market", "1syqofeMd_AxsHzfU7fGKF34BPB0m5GqU", "01. РЫНОК"),
    ("section_ses",    "1jI9NPpXlQWWL8mTY1GufKCzOnNg7HDn_", "02. КАК РАБОТАЕТ СЭС"),
    ("section_equip",  "1JBu91CuVnNvB1vwOOgsdvDRUqVTAikHZ", "03. ОБОРУДОВАНИЕ"),
    ("section_client", "1rZCNDdfBE9hUkZMPhOp9ruxRESvLcBtX", "04. КЛИЕНТ И РЫНОК"),
    ("section_funnel", "13P7N-D5WmQVi5NC5G_xslH5nodQKw0gH", "05. ВОРОНКА/СКРИПТЫ"),
    ("section_finance","1Z8lLouJXK8hOsvZy4Whd9rkKZOkl7ZE_", "06. ФИНАНСЫ"),
    ("section_crm",    "1wNguoBroX1E0-cV9KtXwt0cZ52t3FB2X", "07. ПРОЦЕССЫ/CRM"),
    ("section_epc",    "10ZBtIgHnlZio_NKm--sVCpbfh6SPIhRM", "08. БОЛЬШИЕ СДЕЛКИ"),
    ("section_after",  "1DBsuIksfLkLKetsoE5hQudU1rHnAcNk4", "09. ПОСЛЕ СДЕЛКИ"),
    ("kb_v2",          "1uowsvJTxFLFw3N6CTWOOif0baDMcwIGBpjDe-8uybHo", "БЗ v2.0"),
    ("template",       "14DLRd4HIRRK41UQdQEDhIrd9l7ZIxztAScTnFAdDhs0", "Шаблон модуля"),
]

# Контент промптов (укр. — рабочий контент курсов, НЕ интерфейс)
PROMPTS = {
    "course_section": """Ти — експерт з навчального контенту LK Energy Group.
Компанія: EPC-підрядник СЕС, ексклюзив Wenergy, Одеса.
Трек: {track}. Роль: {role}. Тема: {topic}.

На основі матеріалів створи секцію модуля:
- Заголовок секції
- Вступ (чому важливо для {role})
- Основний контент з таблицями | :-: |
- Блок 💡 "Порада для менеджера" (якщо трек sales)
- Підсумок ✅ (4-6 пунктів через "—")

Стиль: Arial, H1 #1A1A1A, H2 #F5A623. Мова: українська.

Матеріали:
{materials}
""",
    "quiz_generator": """Створи {count} тестових питань для Moodle на основі:
{module_content}

Формат JSON:
[{"question": "...", "type": "multichoice", "answers": [
  {"text": "...", "correct": true, "feedback": "пояснення"},
  {"text": "...", "correct": false},
  {"text": "...", "correct": false},
  {"text": "...", "correct": false}
]}]

Питання практичні. Один правильний варіант. ТІЛЬКИ JSON.
""",
    "summary": """Стисни матеріал у конспект для бази знань LK Energy Group (СЕС, енергетика, продажі).

- 5-8 ключових тез через "—"
- Практичний висновок для треку {track}
- Якщо є цифри/нормативи — зберегти точно

Мова: українська. Без води.

Матеріал:
{content}
""",
    "case_study": """На основі дзвінка/угоди створи навчальний кейс:
{source_data}

1. Ситуація (клієнт, запит, контекст)
2. Що зроблено правильно (3-5 пунктів)
3. Що покращити (2-3 пункти)
4. Ключовий урок
5. Скрипт-відповідь на головне заперечення

Мова: українська. Анонімізувати імена клієнтів.
""",
    "module_fix": """Ти — редактор навчального контенту LK Energy Group (EPC-підрядник СЕС, Одеса).

Завдання: влити правки (файл "++") у поточну версію модуля курсу.

ПОТОЧНА ВЕРСІЯ МОДУЛЯ:
{module_content}

ПРАВКИ (++):
{fixes_content}

Правила:
- Зберегти структуру модуля (заголовки, порядок секцій)
- Інтегрувати правки по місцю, а не дописувати в кінець
- Конфлікт правки з оригіналом → пріоритет у правки
- Стиль: Arial, H1 #1A1A1A + жовта лінія, H2 #F5A623, дефіс замість тире
- Таблиці: шапка #1A1A1A
- Мова: українська

Поверни ПОВНИЙ текст нової версії модуля, без коментарів.
""",
}

SETTINGS = {
    "quiz_questions": "7",
    "collect_hours": "48",
    "approval_timeout_hours": "24",
    "quizzes": "{}",   # JSON: {"М1": {"quiz_id": 0, "category_id": 0}}
}


def seed(conn) -> None:
    """Заполнить пустые конфиг-таблицы начальными данными."""
    if not conn.execute("SELECT 1 FROM sources LIMIT 1").fetchone():
        conn.executemany(
            "INSERT OR IGNORE INTO sources (domain,name,url,type,selector,track) VALUES (?,?,?,?,?,?)",
            SOURCES,
        )
    if not conn.execute("SELECT 1 FROM prompts LIMIT 1").fetchone():
        conn.executemany(
            "INSERT OR IGNORE INTO prompts (name,content) VALUES (?,?)",
            list(PROMPTS.items()),
        )
    if not conn.execute("SELECT 1 FROM drive_folders LIMIT 1").fetchone():
        conn.executemany(
            "INSERT OR IGNORE INTO drive_folders (key,folder_id,title) VALUES (?,?,?)",
            DRIVE_FOLDERS,
        )
    for k, v in SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k, v))
