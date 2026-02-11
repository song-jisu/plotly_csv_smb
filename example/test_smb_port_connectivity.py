import os
import socket
from dotenv import load_dotenv
from pathlib import Path

DOTENV_PATH = Path(__file__).resolve().parent.parent / "nas_smb" / ".env"
load_dotenv(dotenv_path=DOTENV_PATH)

ip = os.getenv("NAS_IP")
port = int(os.getenv("NAS_PORT", "445"))

if not ip:
    raise SystemExit("NAS_IP is not set. Put it in .env or export NAS_IP.")

s = socket.socket()
s.settimeout(5)
try:
    s.connect((ip, port))
    print(f"OK: {ip}:{port} reachable")
except Exception as e:
    print("FAIL:", e)
finally:
    s.close()
