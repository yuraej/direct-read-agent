import ollama
import json
from config import MODEL_NAME, LAW_TOOLS

def run_chat_step_archive(messages: list, archivist_instance, trigger_callback=None) -> tuple:
    """
    Ядро с многошаговым циклом (до 6 итераций) и механизмом Garbage Collection.
    """
    start_len = len(messages)
    
    for i in range(6):
        # Шаг 1: Вызов модели с текущей историей и инструментами
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=LAW_TOOLS
        )
        
        # Добавляем ответ модели в историю (это важно для контекста)
        messages.append(response["message"])

        # Если модель хочет вызвать инструмент
        if response.get("message", {}).get("tool_calls"):
            tool_calls = response["message"]["tool_calls"]
            
            for tool in tool_calls:
                func_name = tool["function"]["name"]
                args = tool["function"]["arguments"]

                if func_name == "load_concept_map":
                    law_id = args.get("law_id")
                    if trigger_callback:
                        trigger_callback(f"Загрузка карты: {law_id}")
                    
                    data = archivist_instance.get_concept_map(law_id)
                    content = json.dumps(data, ensure_ascii=False)
                    messages.append({"role": "tool", "content": content})

                elif func_name == "get_law_articles":
                    law_id = args.get("law_id")
                    required_keys = args.get("required_keys", [])
                    if trigger_callback:
                        trigger_callback(f"Чтение: {law_id} ({len(required_keys)} ст.)")
                    
                    retrieved_dict = archivist_instance.get_articles(law_id=law_id, required_keys=required_keys)
                    content = "\n\n".join(retrieved_dict.values())
                    messages.append({"role": "tool", "content": content})

            # После выполнения всех tool_calls, продолжаем цикл, чтобы модель проанализировала результат
            continue 
        
        else:
            # Модель выдала финальный текстовый ответ (tool_calls нет)
            final_answer = response["message"]["content"]
            
            # --- РЕЖИМ «ЧИСТОГО СТОЛА» ---
            # Оставляем только исходный запрос пользователя и финальный ответ
            # (Включая системный промпт, который идет первым)
            messages = messages[:start_len]
            # Добавляем только финальный ответ ассистента (без технических сообщений о вызовах)
            # Но так как мы сделали messages.append в начале цикла, 
            # в messages[:start_len] сейчас только [system, user, ...user_msgs]
            # Нам нужно добавить последний чистый ответ.
            # Однако, если мы хотим оставить историю диалога корректной,
            # лучше просто вернуть очищенную историю и добавить финальный ответ отдельно.
            return final_answer, messages

    # Если цикл завершился без финального ответа (редкий случай)
    return messages[-1]["content"], messages
