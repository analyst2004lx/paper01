import socket
import time
import math

# Initialization parameters
num_agvs = 3
num_robots = 3
tasks = [[10, 35], [11, 20], [7, 66], [5, 18], [12, 42], [5, 15], [10, 50], [4, 22], [10, 80], [4, 15],
         [9, 28], [3, 12], [15, 70], [9, 32], [12, 50], [3, 10], [15, 45], [3, 8], [11, 55], [7, 18],
         [13, 62], [8, 24], [5, 20], [4, 14], [10, 37]]  # Task processing times and weights
agv_capacities = [50, 70, 100]  # AGV load capacities
agv_start_position = (3, 1)  # Initial position of AGVs
robot_positions = [(0, 3), (3, 3), (6, 3)]  # Fixed positions of Robot Arms

# State initialization
agv_positions = [agv_start_position] * num_agvs
agv_memo = [0] * num_agvs
robot_memo = [0] * num_robots
agv_usage_balance = [0] * num_agvs
robot_usage_balance = [0] * num_robots

def calculate_distance(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def calculate_priority(task_weight, task_wait_time, agv_capacity, agv_distance, agv_usage_balance, robot_usage_balance):
    load_factor = task_weight / agv_capacity
    priority = load_factor + 0.1 * task_wait_time - 0.3 * agv_distance - 0.5 * robot_usage_balance - agv_usage_balance
    return priority

def assign_agv_and_robot(task, agv_positions, robot_positions):
    task_time, task_weight = task
    best_agv = None
    best_robot = None
    best_priority = float('-inf')
    min_time = float('inf')

    for robot_id in range(num_robots):
        for agv_id in range(num_agvs):
            if task_weight > agv_capacities[agv_id]:
                continue
            agv_to_robot_time = calculate_distance(agv_positions[agv_id], robot_positions[robot_id])
            start_time = max(robot_memo[robot_id], agv_memo[agv_id] + agv_to_robot_time)
            finish_time = start_time + task_time
            priority = calculate_priority(task_weight, 0, agv_capacities[agv_id], agv_to_robot_time, agv_usage_balance[agv_id], robot_usage_balance[robot_id])

            if priority > best_priority:
                best_priority = priority
                best_agv = agv_id
                best_robot = robot_id
                min_time = finish_time

    if best_agv is not None and best_robot is not None:
        agv_memo[best_agv] = min_time - task_time + calculate_distance(robot_positions[best_robot], agv_start_position)
        robot_memo[best_robot] = min_time
        agv_positions[best_agv] = agv_start_position
        agv_usage_balance[best_agv] += 1
        robot_usage_balance[best_robot] += 1
        print(f"Task assigned to AGV {best_agv} and Robot Arm {best_robot}")
    else:
        print("No available AGV or Robot Arm found for the task")
    return best_agv, best_robot

def send_task_to_agv(agv_id, task, robot_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    agv_ip = '127.0.0.1'
    agv_port = 6000 + agv_id
    try:
        s.connect((agv_ip, agv_port))
        s.sendall(f'Task {task} to Robot {robot_id}'.encode())
        print(f"Sent task {task} to AGV {agv_id} for Robot {robot_id}")
        return True
    except ConnectionRefusedError as e:
        print(f"Error: {e} (AGV {agv_id}, IP: {agv_ip}, Port: {agv_port})")
        return False
    finally:
        s.close()

def send_task_to_robot_arm(robot_id, task):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    robot_ip = '127.0.0.1'
    robot_port = 7000 + robot_id
    try:
        s.connect((robot_ip, robot_port))
        s.sendall(f'Task {task}'.encode())
        print(f"Sent task {task} to Robot Arm {robot_id}")
        return True
    except ConnectionRefusedError as e:
        print(f"Error: {e} (Robot Arm {robot_id}, IP: {robot_ip}, Port: {robot_port})")
        return False
    finally:
        s.close()

def complete_task(agv_id, robot_id):
    return 10  # Simulated completion time

def schedule_task():
    task_completion_times = []
    for task_idx, task in enumerate(tasks):
        best_agv, best_robot = assign_agv_and_robot(task, agv_positions, robot_positions)
        if best_agv is None or best_robot is None:
            print(f"Failed to assign task {task_idx}")
            continue
        agv_success = send_task_to_agv(best_agv, task, best_robot)
        robot_success = send_task_to_robot_arm(best_robot, task)
        if agv_success and robot_success:
            completion_time = complete_task(best_agv, best_robot)
            task_completion_times.append(completion_time)
        else:
            if not agv_success:
                print(f"Failed to assign task {task_idx} to AGV {best_agv}")
            if not robot_success:
                print(f"Failed to assign task {task_idx} to Robot Arm {best_robot}")

    if task_completion_times:
        return max(task_completion_times)
    else:
        print("No tasks were completed.")
        return 0

def start_scheduler():
    total_time = schedule_task()
    print(f"Total time to complete all tasks: {total_time} seconds")

if __name__ == "__main__":
    print(f"########################This is the scheduler.py########################")
    while True:
        try:
            start_scheduler()
            break
        except Exception as e:
            print(f"Scheduler encountered an error: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)
    print(f"######################## All tasks already finished?? ########################")