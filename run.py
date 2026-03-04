import uvicorn
import sys
import asyncio
import socket

def check_db_port(host, port):
    print(f"Checking DB port {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

if __name__ == "__main__":
    # 1. Настройка Event Loop для Windows (КРИТИЧНО)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("Windows Event Loop Policy applied.")

    # 2. Проверка доступности базы (чтобы не висеть)
    # Порт 5455, так как мы его поменяли в docker-compose
    if not check_db_port("127.0.0.1", 5455):
        print("ERROR: Database port 5455 is not reachable!")
        print("Please run: docker-compose up -d")
        sys.exit(1)

    # ИЗМЕНЕНО: Порт 8001, так как 8000 часто занят
    print("Starting server on http://127.0.0.1:8001 ...")
    
    # 3. Запуск сервера БЕЗ reload (reload часто вызывает зависания на Windows)
    # Если нужно менять код, просто перезапускайте скрипт вручную.
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=False)
