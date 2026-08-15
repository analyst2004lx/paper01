import socket

def robot_arm_listener(robot_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    robot_ip = '127.0.0.1'
    robot_port = 7000 + robot_id
    try:
        s.bind((robot_ip, robot_port))
        s.listen(1)
        print(f"Robot Arm {robot_id} is listening on IP {robot_ip} Port {robot_port}")
    except Exception as e:
        print(f"Failed to bind Robot Arm {robot_id} on IP {robot_ip} Port {robot_port}. Error: {e}")
        return

    while True:
        conn, addr = s.accept()
        data = conn.recv(1024)
        if data:
            print(f"Robot Arm {robot_id} received: {data.decode()}")
            print(f"Robot Arm {robot_id} is processing the task...")
        conn.close()

if __name__ == "__main__":
    print(f"########################This is the robot_arm3.py########################")
    robot_arm_listener(3)  # Robot Arm 3
