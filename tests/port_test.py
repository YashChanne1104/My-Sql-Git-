import socket

host = "ep-silent-frost-azo3yrdg-pooler.c-3.ap-southeast-1.aws.neon.tech"
port = 5432

try:
    sock = socket.create_connection((host, port), timeout=10)
    print("✅ Port is reachable!")
    sock.close()
except Exception as e:
    print("❌ Connection failed:", e)