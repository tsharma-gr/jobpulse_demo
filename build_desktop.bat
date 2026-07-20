@echo off
echo ==============================================
echo Building JobPulse Engine Desktop App...
echo ==============================================

echo 1. Installing PyInstaller...
pip install pyinstaller

echo 2. Compiling the Python Backend into an Executable...
REM We use --onedir to create a folder. This is much more stable for Playwright than --onefile.
REM We include the backend folder so Uvicorn can find the API routes.
pyinstaller --name "JobPulseEngine" --workpath "build2" --onedir --noconsole --clean --noconfirm --add-data "backend;backend" --add-data ".env;." --collect-all uvicorn --collect-all fastapi --collect-all pydantic --collect-all playwright --collect-all sse_starlette --collect-all supabase --collect-all pydantic_settings --collect-all dotenv --collect-all duckduckgo_search --collect-all playwright_stealth --collect-all crawl4ai --collect-all sqlalchemy --collect-all databases JobPulseEngine.py

echo 3. Setting up Playwright Chromium Browsers...
mkdir "dist\JobPulseEngine\browsers"
REM Temporarily set the PLAYWRIGHT_BROWSERS_PATH to the dist folder so it downloads them directly into the packaged app!
set PLAYWRIGHT_BROWSERS_PATH=%CD%\dist\JobPulseEngine\browsers
python -m playwright install chromium

echo ==============================================
echo BUILD COMPLETE!
echo The complete standalone app is located in the "dist\JobPulseEngine" folder.
echo You can zip this folder and send it to your team!
echo ==============================================
pause
