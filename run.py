import uvicorn
import webbrowser
import threading
import time
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    
    print("=" * 65)
    print("  DocImagePrint - Document Image Extractor & Layout Engine")
    print("  Website is now running and ready to share!")
    print("-" * 65)
    print(f"  [1] On this Computer:      http://localhost:{port}")
    print(f"  [2] On Same Wi-Fi/Network: http://{local_ip}:{port}")
    print("=" * 65)
    print("  Anyone on your Wi-Fi (phone, laptop, tablet) can open the link above.")
    print("=" * 65 + "\n")
    
    # Auto launch browser for local user
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
