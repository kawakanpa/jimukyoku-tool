@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo 事務局ツール Webサーバー起動中...
echo ブラウザで http://localhost:8501 を開いてください
echo 他のPCからは http://<このPCのIPアドレス>:8501 でアクセスできます
echo.
echo 終了するには Ctrl+C を押してください
echo.
python -m streamlit run src/app.py --server.address 0.0.0.0 --server.port 8501
pause
