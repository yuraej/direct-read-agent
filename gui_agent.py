import os
import streamlit as st
from archivist import Archivist
import config
import core_chat

st.set_page_config(page_title="Локальный ИИ-Ассистент 2.0", page_icon="🤖", layout="centered")

# --- CSS ИНЪЕКЦИЯ ДЛЯ УВЕЛИЧЕНИЯ ШРИФТОВ, ПЕРЕНОСА СТРОК И ФИКСАЦИИ КНОПОК ---
st.markdown("""
    <style>
    /* 1. Включаем перенос строк для всех блоков кода и убираем скролл */
    code, pre, [data-testid="stCodeBlock"] {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-x: hidden !important;
    }
    
    /* 2. Увеличиваем шрифт в истории чата на 20% (до 1.15rem) */
    [data-testid="stChatMessage"], code, pre {
        font-size: 1.15rem !important;
        line-height: 1.5 !important;
    }
    
    /* 3. Поле ввода вопроса */
    [data-testid="stChatInput"] textarea {
        font-size: 1.3rem !important; 
        line-height: 1.4 !important;
    }
    
    /* 4. Выравнивание кнопок управления справа от ввода */
    .stButton > button {
        padding: 0.5rem 0.2rem !important;
        height: 42px !important;
    }
    </style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "text_for_AI")

# Константа контекстного окна на основе ваших настроек Ollama
MAX_CONTEXT_TOKENS = 128000

st.title("🤖 Локальный ИИ-Ассистент прямого чтения")

# Функция быстрой оценки объема контекста (1 токен ~ 3.3 символа для русского текста)
def estimate_tokens(messages):
    total_chars = 0
    for msg in messages:
        if msg.get("content"):
            total_chars += len(msg["content"])
    return max(1, total_chars // 3)

# 1. СКАНИРОВАНИЕ ДОСТУПНЫХ БАЗ ЗНАНИЙ
if not os.path.exists(DOCUMENTS_DIR):
    st.error(f"Папка {DOCUMENTS_DIR} не найдена! Создайте её и положите туда базы данных.")
    st.stop()

available_folders = [f for f in os.listdir(DOCUMENTS_DIR) if os.path.isdir(os.path.join(DOCUMENTS_DIR, f))]

if not available_folders:
    st.warning("📥 Хранилище пусто. Добавьте папку с материалами внутрь папки `text_for_AI`.")
    st.stop()

# --- ЭЛЕМЕНТ: ОЧИЩЕННАЯ БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("⚙️ Источник данных")
    selected_folder = st.selectbox("Активная база знаний:", available_folders)
    
    st.markdown("---")
    st.subheader("📊 Контекст модели")
    
    if "messages" in st.session_state:
        used_tokens = estimate_tokens(st.session_state.messages)
    else:
        used_tokens = 0
        
    remaining_tokens = max(0, MAX_CONTEXT_TOKENS - used_tokens)
    percentage_used = min(100.0, (used_tokens / MAX_CONTEXT_TOKENS) * 100)
    
    st.progress(percentage_used / 100)
    st.caption(f"Занято токенов: **{used_tokens:,}** / {MAX_CONTEXT_TOKENS:,} ({percentage_used:.2f}%)")
    st.caption(f"Осталось места: **{remaining_tokens:,}** токенов")

# 2. ИНИЦИАЛИЗАЦИЯ И СБРОС СЕССИИ ПРИ СМЕНЕ ДОКУМЕНТА
if "current_folder" not in st.session_state or st.session_state.current_folder != selected_folder:
    st.session_state.current_folder = selected_folder
    
    archivist = Archivist(base_dir=DOCUMENTS_DIR)
    concept_map = archivist.get_concept_map(selected_folder)
    
    if not concept_map:
        st.error(f"Не удалось загрузить карту понятий для папки '{selected_folder}'. Проверьте наличие concept_map.json.")
        st.stop()
        
    system_prompt = config.generate_system_prompt(concept_map)
    st.session_state.messages = [{"role": "system", "content": system_prompt}]
    st.session_state.concept_map = concept_map
    st.rerun()

# --- ЭЛЕМЕНТ: ЦЕНТРАЛЬНАЯ СТАТИЧНАЯ ПЛАШКА-ИНФОРМАТОР ---
st.info(f"📂 **Выбранный источник:** {selected_folder} | Модель работает напрямую с этим документом.")

# 3. ОТОБРАЖЕНИЕ ИСТОРИИ ДИАЛОГА
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"): 
            st.write(msg["content"])
    elif msg["role"] == "assistant" and msg.get("content"):
        with st.chat_message("assistant"): 
            st.code(msg["content"], language="markdown")

# 4. ПОЛЕ ВВОДА И УПРАВЛЕНИЕ (ОБЪЕДИНЕНЫ СПРАВА)
chat_col, btn_col = st.columns([6, 1])

with chat_col:
    user_input = st.chat_input("Задайте вопрос по выбранному источнику...")

with btn_col:
    # Верхняя кнопка: разблокировка при зависании
    if st.button("🚨", help="Разблокировать чат при зависании (удалить последний запрос)", use_container_width=True):
        if "messages" in st.session_state and len(st.session_state.messages) > 0:
            if st.session_state.messages[-1]["role"] == "user":
                st.session_state.messages.pop()
        st.toast("Последний запрос удален. Чат разблокирован!", icon="⚠️")
        st.rerun()
        
    # Нижня кнопка: полная очистка чата
    if st.button("🧹", help="Полностью очистить историю текущего диалога", use_container_width=True):
        if "current_folder" in st.session_state:
            del st.session_state.current_folder
        st.rerun()

# СТАРТ ФУНКЦИОНАЛА ПРИ ВВОДЕ ВОПРОСА
if user_input:
    with st.chat_message("user"): 
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("ИИ анализирует структуру источника..."):
            try:
                archivist = Archivist(base_dir=DOCUMENTS_DIR)
                status_container = st.container()
                
                def show_archive_status(article_id):
                    with status_container:
                        st.info(f"🔍 *Архивариус извлекает монолит с SSD: {article_id.upper()}*")
                
                answer, updated_history = core_chat.run_chat_step_archive(
                    messages=st.session_state.messages,
                    archivist_instance=archivist,
                    law_folder=selected_folder,
                    trigger_callback=show_archive_status
                )
                
                st.code(answer, language="markdown")
                st.session_state.messages = updated_history
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                st.rerun()
                
            except Exception as e:
                st.error(f"Произошла ошибка при обработке запроса: {e}")
