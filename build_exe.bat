@echo off
rem Builds Unbox.exe (one small file, no console). Needs: pip install pyinstaller
cd /d "%~dp0"
python -m PyInstaller --onefile --noconsole --name Unbox --icon "%~dp0unbox.ico" ^
  --exclude-module unittest --exclude-module pydoc --exclude-module email --exclude-module http ^
  --exclude-module xml --exclude-module sqlite3 --exclude-module asyncio --exclude-module multiprocessing ^
  --distpath . --workpath "%TEMP%\unbox_build" --specpath "%TEMP%\unbox_build" unbox.pyw
rmdir /s /q "%TEMP%\unbox_build" 2>nul
echo Done: Unbox.exe
