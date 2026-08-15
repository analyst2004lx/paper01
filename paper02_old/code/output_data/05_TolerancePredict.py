# Re-define the transition matrix DataFrame

# Re-define the input data as a multi-line string (from the user's data)
data = """
AGV_idle AGV ID:1
RobotArm_idle RobotArm ID:1
AGVMovingToRobotArm AGV ID:1
RobotArm_producing RobotArm ID:0
AGVMovingToRobotArm AGV ID:0
RobotArm_producing RobotArm ID:1
AGVAtRobotArm AGV ID:0
AGVMovingToOrigin AGV ID:0
AGVAtOrigin AGV ID:2
AGV_idle AGV ID:2
AGVAtRobotArm AGV ID:1
AGVMovingToOrigin AGV ID:1
AGVAtOrigin AGV ID:0
AGV_idle AGV ID:0
AGVAtOrigin AGV ID:1
AGV_idle AGV ID:1
RobotArm_idle RobotArm ID:2
AGVMovingToRobotArm AGV ID:0
RobotArm_producing RobotArm ID:2
RobotArm_idle RobotArm ID:1
AGVMovingToRobotArm AGV ID:1
RobotArm_producing RobotArm ID:1
AGVAtRobotArm AGV ID:0
AGVMovingToOrigin AGV ID:0
AGVAtRobotArm AGV ID:1
AGVMovingToOrigin AGV ID:1
AGVAtOrigin AGV ID:1
AGV_idle AGV ID:1
RobotArm_idle RobotArm ID:1
AGVMovingToRobotArm AGV ID:1
RobotArm_producing RobotArm ID:1
AGVAtOrigin AGV ID:0
AGV_idle AGV ID:0
AGVAtRobotArm AGV ID:1
AGVMovingToOrigin AGV ID:1
RobotArm_idle RobotArm ID:2
AGVMovingToRobotArm AGV ID:0
RobotArm_producing RobotArm ID:2
AGVAtOrigin AGV ID:1
AGV_idle AGV ID:1
RobotArm_idle RobotArm ID:0
AGVMovingToRobotArm AGV ID:1
RobotArm_producing RobotArm ID:0
RobotArm_idle RobotArm ID:1
AGVAtRobotArm AGV ID:0
AGVMovingToOrigin AGV ID:0
AGVAtRobotArm AGV ID:1
AGVMovingToOrigin AGV ID:1
AGVAtOrigin AGV ID:0
AGV_idle AGV ID:0
AGVAtOrigin AGV ID:1
AGV_idle AGV ID:1
RobotArm_idle RobotArm ID:0
RobotArm_idle RobotArm ID:2
"""

# Repeat the parsing, DataFrame creation, and state prediction steps
import pandas as pd
import numpy as np
import re

# Step 1: Re-parse the data as before
parsed_data = []
pattern = re.compile(r'(\w+)\s+(\w+)\s+ID:(\d+)')  # Regular expression to match the state, device type, and ID

for line in data.strip().split("\n"):
    match = pattern.match(line)
    if match:
        state = match.group(1)
        device_type = match.group(2)
        device_id = int(match.group(3))
        parsed_data.append({'State': state, 'Device Type': device_type, 'Device ID': device_id})

# Convert to DataFrame
df = pd.DataFrame(parsed_data)

# Extract the state sequence from the DataFrame
state_sequence = df['State'].tolist()

# Get the unique states and create mappings
unique_states = list(set(state_sequence))
state_to_index = {state: idx for idx, state in enumerate(unique_states)}
index_to_state = {idx: state for state, idx in state_to_index.items()}

# Initialize the transition matrix with zeros
n_states = len(unique_states)
transition_matrix = np.zeros((n_states, n_states))

# Populate the transition matrix based on the state sequence
for i in range(len(state_sequence) - 1):
    current_state = state_sequence[i]
    next_state = state_sequence[i + 1]
    current_index = state_to_index[current_state]
    next_index = state_to_index[next_state]
    transition_matrix[current_index, next_index] += 1

# Normalize the transition matrix to obtain probabilities
transition_matrix = transition_matrix / transition_matrix.sum(axis=1, keepdims=True)

# Convert the transition matrix to a DataFrame for better visualization
transition_matrix_df = pd.DataFrame(transition_matrix, index=unique_states, columns=unique_states)

# Step 7: Predict the next state using the Markov Chain model
def predict_next_state(current_state, transition_matrix_df, state_to_index, index_to_state):
    # Get the current state's index
    current_index = state_to_index.get(current_state)
    
    if current_index is None:
        raise ValueError(f"State '{current_state}' not found in the state list.")
    
    # Get the transition probabilities for the current state
    transition_probabilities = transition_matrix_df.iloc[current_index].values
    
    # Find the index of the maximum probability (i.e., the most likely next state)
    next_index = np.argmax(transition_probabilities)
    
    # Get the name of the next state
    next_state = index_to_state[next_index]
    
    return next_state

# Re-define the current state and predicted next state
current_state = "AGV_idle"
next_state = predict_next_state(current_state, transition_matrix_df, state_to_index, index_to_state)

# Step 8: Check for abnormal transition from "AGV_idle" to the predicted next state
def check_for_abnormal_transition(current_state, next_state, transition_matrix_df, state_to_index, tolerance_threshold=0.1):
    # Get the indices of the current and next states
    current_index = state_to_index.get(current_state)
    next_index = state_to_index.get(next_state)
    
    if current_index is None or next_index is None:
        raise ValueError("Current or next state not found in the state list.")
    
    # Get the transition probability from the current state to the next state
    transition_probability = transition_matrix_df.iloc[current_index, next_index]
    
    # Check if the transition probability is below the tolerance threshold
    if transition_probability < tolerance_threshold:
        return True  # This is an abnormal transition
    else:
        return False  # This is a normal transition

# Example: Check for abnormal transition from "AGV_idle" to the predicted next state
tolerance_threshold = 0.1  # Set the tolerance threshold
is_abnormal = check_for_abnormal_transition(current_state, next_state, transition_matrix_df, state_to_index, tolerance_threshold)

# Display the result
is_abnormal
