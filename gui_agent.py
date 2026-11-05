import os
import streamlit as st
from archivist import Archivist
import config
import core_chat

st.set_page_config(page_title="Локальный ИИ-Ассистент 2.0", page_icon="🤖", layout="centered")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "text_for_AI")

st.title("🤖 Локальный Юридический Ассистент")

# 1. СКАНИРОВАНИЕ ДОСТУПНЫХ БАЗ ЗНАНИЙ
if not os.path.exists(DOCUMENTS_DIR):
    st.error(f"Папка {DOCUMENTS_DIR} не найдена! Создайте её и положите туда базы данных.")
    st.stop()

# Находим все подпапки внутри text_for_AI (например, zozpp)
available_folders = [f for f in os.listdir(DOCUMENTS_DIR) if os.path.isdir(os.path.join(DOCUMENTS_DIR, f))]

if not available_folders:
    st.warning("📥 Хранилище пусто. Добавьте папку с законом (например, 'zozpp') внутрь папки `text_for_AI`.")
    st.stop()

# Выпадающий список для выбора активного документа
selected_folder = st.selectbox("Выберите активную базу знаний / закон:", available_folders)

# 2. ИНИЦИАЛИЗАЦИЯ И СБРОС СЕССИИ ПРИ СМЕНЕ ДОКУМЕНТА
if "current_folder" not in st.session_state or st.session_state.current_folder != selected_folder:
    st.session_state.current_folder = selected_folder
    
    # Инициализируем Архивариуса для чтения карты понятий
    archivist = Archivist(base_dir=DOCUMENTS_DIR)
    concept_map = archivist.get_concept_map(selected_folder)
    
    if not concept_map:
        st.error(f"Не удалось загрузить карту понятий для папки '{selected_folder}'. Проверьте наличие concept_map.json.")
        st.stop()
        
    # Генерируем жесткий системный промпт со встроенной картой понятий
    system_prompt = config.generate_system_prompt(concept_map)
    
    # Записываем первое системное сообщение в историю (оно будет висеть в окне всегда)
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

# 3. ОТОБРАЖЕНИЕ ИСТОРИИ ДИАЛОГА (Пропускаем системный промпт, показываем только чат)
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"): 
            st.write(msg["content"])
    elif msg["role"] == "assistant" and msg.get("content"):
        with st.chat_message("assistant"): 
            st.write(msg["content"])

# 4. ПОЛЕ ВВОДА ВОПРОСА И СТАРТ ФУНКЦИОНАЛА
if user_input := st.chat_input("Задайте вопрос по выбранному документу..."):
    # Выводим вопрос пользователя на экран и сохраняем в историю
    with st.chat_message("user"): 
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Начинаем генерацию ответа ИИ
    with st.chat_message("assistant"):
        with st.spinner("ИИ анализирует карту понятий..."):
            try:
                archivist = Archivist(base_dir=DOCUMENTS_DIR)
                
                # Создаем контейнер для красивого вывода плашек прямо во время работы
                status_container = st.container()
                
                # Функция-колбэк, которую core_chat вызовет, если gemma4 запросит статью
                def show_archive_status(article_id):
                    with status_container:
                        st.info(f"🔍 *Архивариус извлекает монолит с SSD: {article_id.upper()}*")
                
                # Вызываем наше новое ядро чата с поддержкой "чистого стола"
                answer, updated_history = core_chat.run_chat_step_archive(
                    messages=st.session_state.messages,
                    archivist_instance=archivist,
                    law_folder=selected_folder,
                    trigger_callback=show_archive_status
                )
                
                # Выводим готовый ответ пользователю в Markdown
                st.write(answer)
                
                # Фиксируем очищенную историю (без тяжелых статей) в сессии
                st.session_state.messages = updated_history
                # Добавляем финальный ответ ассистента в историю диалога
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                st.error(f"Произошла ошибка при обработке запроса: {e}")
