import socket

def agv_listener(agv_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    agv_ip = '127.0.0.1'
    agv_port = 6000 + agv_id
    try:
        s.bind((agv_ip, agv_port))
        s.listen(1)
        print(f"AGV {agv_id} is listening on IP {agv_ip} Port {agv_port}")
    except Exception as e:
        print(f"Failed to bind AGV {agv_id} on IP {agv_ip} Port {agv_port}. Error: {e}")
        return

    while True:
        conn, addr = s.accept()
        data = conn.recv(1024)
        if data:
            print(f"AGV {agv_id} received: {data.decode()}")
            print(f"AGV {agv_id} is processing the task...")
        conn.close()

if __name__ == "__main__":
    print(f"########################This is the agv3.py########################")
    agv_listener(3)  # AGV3
