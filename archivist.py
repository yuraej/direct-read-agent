import sqlite3
import re


class Archivist:
    def __init__(self, db_path="library.db", base_dir=None):
        """Инициализация Архивариуса (base_dir оставлен для совместимости с gui_agent.py)"""
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        """Автоматически создает файл БД и таблицы, если их еще нет"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS laws (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    scope TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    law_id TEXT NOT NULL,
                    node_key TEXT NOT NULL,
                    concept_summary TEXT NOT NULL,
                    full_text TEXT NOT NULL,
                    PRIMARY KEY (law_id, node_key),
                    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source_law TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    target_law TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    trigger_note TEXT NOT NULL,
                    PRIMARY KEY (source_law, source_key, target_law, target_key),
                    FOREIGN KEY (source_law, source_key) REFERENCES nodes(law_id, node_key) ON DELETE CASCADE,
                    FOREIGN KEY (target_law, target_key) REFERENCES nodes(law_id, node_key) ON DELETE CASCADE
                )
            """)

    def get_library_overview(self) -> list:
        """Корневая карта всех законов"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, title, scope FROM laws").fetchall()
            return [dict(r) for r in rows]

    def get_concept_map(self, law_folder: str) -> list:
        """Достает карту понятий из БД вместо concept_map.json"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT node_key as article, concept_summary as description FROM nodes WHERE law_id = ?",
                (law_folder,)
            ).fetchall()
            return [dict(r) for r in rows]

    def _normalize_key(self, raw_key: str) -> str:
        """Оригинальный фильтр ключей"""
        raw_key = raw_key.strip()
        match = re.search(r'(?:ст\.?|статья)\s*([0-9]+(?:-[0-9]+)?)', raw_key, re.IGNORECASE)
        if match:
            return f"статья{match.group(1)}"
        fallback_match = re.search(r'([0-9]+(?:-[0-9]+)?)', raw_key)
        if fallback_match:
            return f"статья{fallback_match.group(1)}"
        return raw_key.lower().replace(" ", "")

    def get_articles(self, law_folder: str, required_keys: list) -> dict:
        """Достает статьи из БД + прикрепляет ссылки на постановления/другие статьи"""
        results = {}
        with self._get_conn() as conn:
            for raw_key in required_keys:
                target_article = self._normalize_key(raw_key)
                print(f"[Архивариус БД] Запрос ИИ: '{raw_key}' ➡ Раздел: '{law_folder}', Ключ: '{target_article}'")

                row = conn.execute(
                    "SELECT full_text FROM nodes WHERE law_id = ? AND node_key = ?",
                    (law_folder, target_article)
                ).fetchone()

                if not row:
                    results[target_article] = f"[СИСТЕМНОЕ УВЕДОМЛЕНИЕ] Документ '{target_article}' отсутствует в разделе '{law_folder}'."
                    continue

                text = row["full_text"]

                links = conn.execute("""
                    SELECT target_law, target_key, trigger_note 
                    FROM edges 
                    WHERE source_law = ? AND source_key = ?
                """, (law_folder, target_article)).fetchall()

                if links:
                    links_block = "\n\n--- СВЯЗАННЫЕ НОРМЫ И ПОДЗАКОННЫЕ АКТЫ ---\n"
                    for link in links:
                        links_block += f"• Раздел: '{link['target_law']}', Ключ: '{link['target_key']}' — {link['trigger_note']}\n"
                    text += links_block

                results[target_article] = text

        return results
