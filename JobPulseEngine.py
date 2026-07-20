import os
import sys
import threading
import time
import webbrowser
import uvicorn

def open_browser():
    """Wait for the server to start, then open the browser."""
    time.sleep(3)
    # The Vercel URL the user provided
    webbrowser.open("https://jobpulse-demo.vercel.app/")
    print("Launched JobPulse AI Dashboard in your web browser!")

def main():
    # Detect if we are running in a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # We are running as a compiled PyInstaller .exe
        application_path = sys._MEIPASS
        # Playwright looks for PLAYWRIGHT_BROWSERS_PATH.
        # We will package the browsers folder into the same directory as the .exe
        exe_dir = os.path.dirname(sys.executable)
        browsers_path = os.path.join(exe_dir, "browsers")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
        
        # We also need to make sure the app can find the backend module
        sys.path.insert(0, application_path)
    
    # Start the browser thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start the FastAPI server
    print("Starting JobPulse AI Engine...")
    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
