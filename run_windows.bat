@echo off
chcp 65001 >nul
cd /d %~dp0
python -c "import streamlit" 2>nul
if errorlevel 1 (
  echo [缺少依赖] 当前 Python 环境未安装 Streamlit。
  echo 请先运行: pip install -r requirements.txt
  pause
  exit /b 1
)
python -m streamlit run app.py
