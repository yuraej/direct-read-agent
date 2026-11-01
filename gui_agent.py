import os
from pypdf import PdfReader
import ollama
import streamlit as st

# Настройка страницы чата
st.set_page_config(page_title="ИИ-Агент прямого чтения", page_icon="🤖", layout="centered")

# Путь к папке с документами
DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "text_for_AI")
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

SYSTEM_PROMPT = (
    "Вы — ИИ-Агент прямого чтения (Direct-Read Agent). Ваши ответы должны основываться "
    "исключительно на тексте прочитанных файлов. Если пользователь спрашивает о документе, "
    "используйте инструмент чтения. Будьте точны, честны и не выдумывайте факты, которых нет в тексте."
)

def read_local_file(filename: str) -> str:
    """Инструмент прямого чтения файлов из папки text_for_AI."""
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(DOCUMENTS_DIR, safe_filename)
    
    if not os.path.exists(file_path):
        return f"Ошибка: Файл '{safe_filename}' не найден в папке {DOCUMENTS_DIR}."
    
    ext = os.path.splitext(safe_filename)[1].lower()
    
    try:
        if ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        elif ext == '.pdf':
            reader = PdfReader(file_path)
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Страница {i+1} ---\n{page_text}")
            return "\n".join(text_parts) if text_parts else "PDF файл пуст или не содержит печатного текста."
            
        else:
            return f"Ошибка: Формат {ext} не поддерживается. Разрешены только .txt, .md, .pdf."
            
    except Exception as e:
        return f"Ошибка при чтении файла: {str(e)}"

# Заголовок интерфейса
st.title("🤖 ИИ-Агент прямого чтения")
st.caption(f"Локальная модель: **gemma4** | Папка документов: `{DOCUMENTS_DIR}`")

# Инициализация истории сообщений в сессии браузера
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Отображение истории чата (кроме системного промпта)
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            st.write(msg["content"])

# Поле ввода для пользователя
if user_input := st.chat_input("Задайте вопрос по вашим документам..."):
    # Отображаем вопрос пользователя
    with st.chat_message("user"):
        st.write(user_input)
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Определение инструментов
    tools = [{
        'type': 'function',
        'function': {
            'name': 'read_local_file',
            'description': 'Читает полное содержимое указанного файла (.txt, .md, .pdf) из локальной папки документов.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'filename': {
                        'type': 'string',
                        'description': 'Имя файла с расширением (например, report.pdf, notes.txt)',
                    },
                },
                'required': ['filename'],
            },
        },
    }]
    
    # Генерация ответа ИИ
    with st.chat_message("assistant"):
        with st.spinner("ИИ думает..."):
            try:
                # Первый запрос к модели
                response = ollama.chat(
                    model='gemma4',
                    messages=st.session_state.messages,
                    tools=tools
                )
                
                # Проверяем вызов инструмента
                if response.message.tool_calls:
                    for tool in response.message.tool_calls:
                        if tool.function.name == 'read_local_file':
                            filename = tool.function.arguments.get('filename')
                            
                            # Визуальный маркер вызова инструмента в чате
                            st.info(f"🔍 *ИИ читает файл: {filename}*")
                            
                            file_content = read_local_file(filename)
                            
                            # Добавляем вызов инструмента и его ответ в историю
                            st.session_state.messages.append(response.message)
                            st.session_state.messages.append({
                                'role': 'tool',
                                'content': file_content,
                                'name': tool.function.name
                            })
                            
                            # Финальный генеративный ответ
                            final_response = ollama.chat(
                                model='gemma4',
                                messages=st.session_state.messages
                            )
                            st.write(final_response.message.content)
                            st.session_state.messages.append(
                                {"role": "assistant", "content": final_response.message.content}
                            )
                else:
                    # Обычный ответ, если файл читать не потребовалось
                    st.write(response.message.content)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response.message.content}
                    )
            except Exception as e:
                st.error(f"Произошла ошибка: {e}")
