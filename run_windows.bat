@echo off
chcp 65001 >nul
cd /d %~dp0

echo [1/3] 检查 Streamlit...
python -c "import streamlit" 2>nul
if errorlevel 1 (
  echo [缺少依赖] 当前 Python 环境未安装 Streamlit。
  echo 请先运行: pip install -r requirements.txt
  pause
  exit /b 1
)

echo [2/3] 检查导航结构...
python navigation_structure_test.py
if errorlevel 1 (
  echo [结构错误] 请修复工程导航结构后再启动。
  pause
  exit /b 1
)

echo [3/3] 启动碳算智调 Web 原型...
python -m streamlit run app.py
