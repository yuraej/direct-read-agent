@echo off
title ИИ-Агент Чат
cd /d D:\AI_AGENT
echo Запуск графического интерфейса ИИ-Агента...
.\.venv\Scripts\streamlit.exe run gui_agent.py
pause
