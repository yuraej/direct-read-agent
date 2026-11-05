import ollama
from archivist import Archivist
from config import LAW_TOOLS

def run_chat_step_archive(messages: list, archivist_instance: Archivist, law_folder: str, trigger_callback=None) -> tuple:
    """
    Ядро взаимодействия с моделью gemma4 через Native Tool Calling с режимом 'Чистого стола'.
    Принимает историю сообщений, экземпляр Архивариуса и имя активной папки.
    Возвращает: (финальный_текст_ответа, обновленная_чистая_история_сообщений)
    """
    
    # Шаг 1: Первичный запрос к Ollama с передачей паспорта инструментов
    response = ollama.chat(
        model="gemma4",
        messages=messages,
        tools=LAW_TOOLS
    )
    
    # Шаг 2: Проверяем, решила ли модель вызвать инструмент (Архив)
    if response.get("message", {}).get("tool_calls"):
        tool_calls = response["message"]["tool_calls"]
        
        # Добавляем технический ответ модели (с намерением вызвать инструмент) в историю
        messages.append(response["message"])
        
        # Обрабатываем каждый вызов инструмента от модели
        for tool in tool_calls:
            if tool["function"]["name"] == "get_law_articles":
                # Извлекаем аргументы, которые сгенерировала gemma4
                args = tool["function"]["arguments"]
                required_keys = args.get("required_keys", [])
                folder = args.get("law_folder", law_folder) # берем из ИИ или системный фолбэк
                
                # Запускаем визуальный колбэк в интерфейсе, если он передан
                if trigger_callback:
                    for key in required_keys:
                        trigger_callback(key)
                
                # Обращаемся к Архивариусу за монолитами статей
                retrieved_dict = archivist_instance.get_articles(law_folder=folder, required_keys=required_keys)
                
                # СКЛЕЙКА: Переводим словарь Архивариуса в один сплошной Markdown-текст для ИИ
                clean_articles_text = "\n\n".join(retrieved_dict.values())
                
                # Упаковываем прочитанный текст в сообщение с ролью 'tool'
                tool_response_message = {
                    "role": "tool",
                    "content": clean_articles_text
                }
                messages.append(tool_response_message)
        
        # Шаг 3: Повторный вызов Ollama — модель изучает выложенные на стол статьи и пишет итог
        final_response = ollama.chat(
            model="gemma4",
            messages=messages
        )
        
        answer = final_response["message"]["content"]
        
        # =====================================================================
        # 🧼 РЕЖИМ «ЧИСТОГО СТОЛА» (GARBAGE COLLECTION)
        # =====================================================================
        # Избавляемся от тяжелых данных на лету:
        # Мы удаляем из истории два последних сообщения: технический Tool Call модели 
        # и тяжелый текст статьи с ролью 'tool'. 
        # Модель выдала ответ — контекст больше не должен засоряться монолитами.
        messages.pop()  # Стираем сообщение 'tool' (текст статей)
        messages.pop()  # Стираем сообщение 'assistant' (технический вызов инструмента)
        
        return answer, messages

    else:
        # Если модель решила, что статьи ей не нужны (отвечает по общему контексту или карте понятий)
        answer = response["message"]["content"]
        return answer, messages
