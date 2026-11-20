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
DATABASE_PATH = os.path.join(BASE_DIR, "library.db")

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
if not os.path.exists(DATABASE_PATH):
    st.error(f"Файл БД {DATABASE_PATH} не найден!")
    st.stop()

archivist = Archivist(db_path=DATABASE_PATH)
library_overview = archivist.get_library_overview()

if not library_overview:
    st.error("📥 База данных пуста. Добавьте разделы в library.db.")
    st.stop()

# --- ЭЛЕМЕНТ: ОЧИЩЕННАЯ БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("⚙️ Источник данных")
    
    # Добавляем опцию "Все разделы БД (автонавигация)"
    selected_folder = st.selectbox(
        "Активная база знаний:", 
        ["Все разделы БД (автонавигация)"] + [f["id"] for f in library_overview],
        index=0
    )
    
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
    
    # Если выбран "Все разделы", загружаем корневую карту
    if selected_folder == "Все разделы БД (автонавигация)":
        system_prompt = config.generate_system_prompt(library_overview)
        active_concept_map = None
        active_law_id = None
    else:
        # Иначе загружаем карту понятий для выбранного раздела
        active_concept_map = archivist.get_concept_map(selected_folder)
        system_prompt = config.generate_system_prompt(library_overview, 
                                                     active_concept_map=active_concept_map,
                                                     active_law_id=selected_folder)
    
    st.session_state.messages = [{"role": "system", "content": system_prompt}]
    st.session_state.concept_map = active_concept_map
    st.rerun()

# --- ЭЛЕМЕНТ: ЦЕНТРАЛЬНАЯ СТАТИЧНАЯ ПЛАШКА-ИНФОРМАТОР ---
if selected_folder == "Все разделы БД (автонавигация)":
    st.info("🌐 **Режим автонавигации:** ИИ может переключаться между всеми разделами БД")
else:
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
        
    # Нижняя кнопка: полная очистка чата
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
                # Вызываем ядро без параметра law_folder
                archivist = Archivist(db_path=DATABASE_PATH)
                status_container = st.container()
                
                def show_archive_status(article_id):
                    with status_container:
                        st.info(f"🔍 *Архивариус извлекает монолит с SSD: {article_id.upper()}*")
                
                answer, updated_history = core_chat.run_chat_step_archive(
                    messages=st.session_state.messages,
                    archivist_instance=archivist,
                    trigger_callback=show_archive_status
                )
                
                st.code(answer, language="markdown")
                st.session_state.messages = updated_history
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                st.rerun()
                
            except Exception as e:
                st.error(f"Произошла ошибка при обработке запроса: {e}")
