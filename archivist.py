import os
import json
import re 

class Archivist:
    def __init__(self, base_dir="text_for_AI"):
        """Инициализация Архивариуса с указанием корневой папки знаний"""
        self.base_dir = base_dir 

    def get_concept_map(self, law_folder: str) -> list:
        """Считывает карту понятий (шпаргалку) из любой указанной подпапки"""
        path = os.path.join(self.base_dir, law_folder, "concept_map.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Архивариус] [Ошибка] Не удалось загрузить карту понятий из {path}: {e}")
            return []

    def _normalize_key(self, raw_key: str) -> str:
        """
        Бронебойный фильтр: принимает хаотичные маркеры модели (ст.20, СТАТЬЯ 9-1)
        и приводит строго к неуязвимому ключу нижнего регистра: 'статьяX'
        """
        raw_key = raw_key.strip()
        
        # Регулярка для вытягивания 'ст'/'статья' и номера с дефисом
        match = re.search(r'(?:ст\.?|статья)\s*([0-9]+(?:-[0-9]+)?)', raw_key, re.IGNORECASE) 

        if match: 
            return f"статья{match.group(1)}" 

        # Защитный fallback для голых цифр
        fallback_match = re.search(r'([0-9]+(?:-[0-9]+)?)', raw_key)
        if fallback_match:
            return f"статья{fallback_match.group(1)}"

        return raw_key.lower().replace(" ", "")

    def get_articles(self, law_folder: str, required_keys: list) -> dict:
        """
        Основной метод извлечения монолитов статей с диска.
        Заходит в нужную папку, нормализует ключи и собирает текст.
        """
        body_path = os.path.join(self.base_dir, law_folder, "law_body.json")
        results = {} 

        try:
            with open(body_path, "r", encoding="utf-8") as f:
                raw_body = json.load(f)
                # Страховка: принудительно нормализуем ключи загруженного словаря в lower_case
                law_body = {str(k).lower().strip().replace(" ", ""): v for k, v in raw_body.items()}
        except Exception as e:
            return {"ошибка": f"Не удалось прочитать базу данных по пути {body_path}: {str(e)}"} 

        for raw_key in required_keys: 
            target_article = self._normalize_key(raw_key)
            print(f"[Архивариус] Запрос ИИ: '{raw_key}' ➡️ Ключ поиска: '{target_article}'") 

            if target_article in law_body:
                results[target_article] = law_body[target_article]
            else:
                results[target_article] = f"[СИСТЕМНОЕ УВЕДОМЛЕНИЕ] Документ '{target_article}' отсутствует в базе данных '{law_folder}'." 

        return results 


if __name__ == "__main__": 
    print("--- ТЕСТИРОВАНИЕ НОВОГО УНИВЕРСАЛЬНОГО АРХИВАРИУСА ---") 
    archivist = Archivist() 
    cmap = archivist.get_concept_map("zozpp")
    print(f"Успешно прочитано концептов: {len(cmap)}")
