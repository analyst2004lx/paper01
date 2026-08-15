import socket
import tkinter as tk
from threading import Thread
import ast

# Initialize grid parameters
grid_size = (7, 5)  # Grid dimensions (rows x cols)
agv_positions = {1: (3, 1), 2: (3, 1), 3: (3, 1)}  # Initial AGV positions
robot_positions = {1: (0, 3), 2: (3, 3), 3: (6, 3)}  # Robot Arm positions
agv_states = {1: 'idle', 2: 'idle', 3: 'idle'}
robot_states = {1: 'idle', 2: 'idle', 3: 'idle'}

# Create tkinter window
root = tk.Tk()
root.title("AGV and Robot Arm Monitoring")

canvas = tk.Canvas(root, width=500, height=500, bg='white')
canvas.grid(row=0, column=0, rowspan=6)

# Labels for displaying states
agv_state_label = tk.Label(root, text="AGV States: ", font=("Arial", 12))
agv_state_label.grid(row=0, column=1, sticky='w')

robot_state_label = tk.Label(root, text="Robot Arm States: ", font=("Arial", 12))
robot_state_label.grid(row=1, column=1, sticky='w')

# Function to update the grid with AGV and Robot Arm positions
def update_grid():
    print("Updating grid...")
    canvas.delete("all")
    cell_size = 50

    # Draw grid lines
    for row in range(grid_size[0]):
        for col in range(grid_size[1]):
            canvas.create_rectangle(col * cell_size, row * cell_size, (col + 1) * cell_size, (row + 1) * cell_size, outline='gray')

    # Plot AGVs
    for agv_id, pos in agv_positions.items():
        color = 'green' if agv_states[agv_id] == 'idle' else 'orange'  # Green if idle, orange if assigned
        print(f"AGV-{agv_id} at position {pos} with state {agv_states[agv_id]}")  # Debugging statement
        canvas.create_rectangle(pos[1] * cell_size, (grid_size[0] - pos[0]) * cell_size,
                                (pos[1] + 1) * cell_size, (grid_size[0] - pos[0] + 1) * cell_size,
                                outline='black', fill=color)
        canvas.create_text((pos[1] + 0.5) * cell_size, (grid_size[0] - pos[0] + 0.5) * cell_size,
                           text=f'AGV-{agv_id}\n({agv_states[agv_id]})')

    # Plot Robot Arms
    for robot_id, pos in robot_positions.items():
        color = 'blue' if robot_states[robot_id] == 'idle' else 'red'  # Blue if idle, red if producing
        print(f"Robot-{robot_id} at position {pos} with state {robot_states[robot_id]}")  # Debugging statement
        canvas.create_rectangle(pos[1] * cell_size, (grid_size[0] - pos[0]) * cell_size,
                                (pos[1] + 1) * cell_size, (grid_size[0] - pos[0] + 1) * cell_size,
                                outline='black', fill=color)
        canvas.create_text((pos[1] + 0.5) * cell_size, (grid_size[0] - pos[0] + 0.5) * cell_size,
                           text=f'Robot-{robot_id}\n({robot_states[robot_id]})')

    # Update AGV and Robot Arm status labels
    agv_state_label.config(text=f"AGV States: " + ", ".join([f"AGV-{i}: {agv_states[i]}" for i in agv_states]))
    robot_state_label.config(text=f"Robot Arm States: " + ", ".join([f"Robot-{i}: {robot_states[i]}" for i in robot_states]))

# Function to handle incoming data and update positions and states
def handle_data(data):
    print(f"Received data: {data}")  # Debugging statement to see incoming data
    try:
        # Attempt to parse the data string properly, considering the specific format
        if "Task" in data:
            parts = data.split(' to ')
            if len(parts) == 2:
                task_str = parts[0].replace('Task ', '').strip()
                task = ast.literal_eval(task_str)  # Safely evaluate the task list from the string
                
                robot_part = parts[1].strip()
                if robot_part.startswith('Robot'):
                    robot_id = int(robot_part.split(' ')[1])
                    agv_id = (task[1] % 3) + 1  # Simple mapping for demo purposes
                    agv_states[agv_id] = 'assigned'
                    robot_states[robot_id] = 'producing'
                    update_grid()
                else:
                    print("Error: Received data format does not match expected format.")
        else:
            print("No recognizable task information found in received data.")
    except Exception as e:
        print(f"Error processing message: {e}")

# Listener function to receive data
def listener_server():
    listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener_socket.bind(('127.0.0.1', 6000))  # Listening on port 6000
    except OSError as e:
        print(f"Error binding socket: {e}")
        return
    listener_socket.listen(5)
    print("Monitor listening on port 6000")

    while True:
        conn, addr = listener_socket.accept()
        print(f"Connected to {addr}")
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"Received raw data: {data.decode('utf-8')}")  # Print raw data for debugging
                handle_data(data.decode('utf-8'))  # Decode and process data
        except Exception as e:
            print(f"Connection to {addr} lost with error: {e}")
        finally:
            conn.close()

# Main function to start the listener and visualization
def main():
    # Create a separate thread for the listener
    listener_thread = Thread(target=listener_server, daemon=True)
    listener_thread.start()

    # Start tkinter main loop
    root.mainloop()

if __name__ == "__main__":
    main()
