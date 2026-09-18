"""
FinOps Cloud Waste Hunter & Auto-Remediator - Application Launcher
Launches FastAPI backend server and automatically opens browser dashboard.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import sys
import time
import socket
import webbrowser
import threading
import uvicorn

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def find_free_port(start_port: int = 8080, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def open_browser(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[!] Please open your browser manually at: {url} ({e})")


def print_banner(port: int):
    print("=" * 76)
    print("  ⚡ FinOps Cloud Waste Hunter & Auto-Remediator")
    print("  Course:      ISWE309L Cloud Computing | Slot: A1 + TA1")
    print("  Institution: Vellore Institute of Technology (VIT)")
    print("  Project Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)")
    print("=" * 76)
    print(f"  [+] Local Web Dashboard:   http://localhost:{port}/")
    print(f"  [+] REST API Swagger Docs: http://localhost:{port}/docs")
    print(f"  [+] Modules Supported:     1 (Monitoring) to 7 (GitOps PR)")
    print("=" * 76)
    print("  Press CTRL+C anytime to stop the application.\n")


def main():
    port = find_free_port(8080)
    url = f"http://localhost:{port}/"

    print_banner(port)

    # Automatically launch browser in background
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    # Launch Uvicorn server
    from app.server import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
