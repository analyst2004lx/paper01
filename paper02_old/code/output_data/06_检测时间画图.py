import matplotlib.pyplot as plt
import numpy as np

# Data from the table
attack_interval = [10000, 5000, 2500, 1250, 625, 313, 156, 78, 39, 20, 10, 5]
detection_time_flow = [np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, 1394, 1440, 1404, 1400, 1400, 1395]
detection_time_new = [3, 4, 3, 3, 4, 4, 4, 78, 40, 40, 30, 15]

flow_measurement_color = '#c24d4d'  # Red color for flow measurement method
new_method_color = '#92b774'        # Green color for the new method

# Create the plot
plt.figure(figsize=(10, 6))

# Plot the first line (flow measurement method)
plt.plot(attack_interval, detection_time_new, label='Detection Time (new method)', marker='o', color=new_method_color)
# Filter out 'inf' values for plotting
valid_indices = [i for i, x in enumerate(detection_time_flow) if not np.isinf(x)]
valid_attack_interval = [attack_interval[i] for i in valid_indices]
valid_detection_time_flow = [detection_time_flow[i] for i in valid_indices]
plt.plot(valid_attack_interval, valid_detection_time_flow, label='Detection Time (flow measurement method)', marker='s', color=flow_measurement_color)

# Set axis scales and labels
plt.xscale('log')  # Use logarithmic scale for attack interval to better represent the wide range
plt.xlabel('Attack Average Interval Time (milliseconds) per abnormal data')
plt.ylabel('Detection Time (milliseconds)')
plt.title('Detection Time Comparison between Flow Measurement Method and New Method')

# Add legend
plt.legend()

# Show the grid for better readability
plt.grid(True, which="both", linestyle='--', linewidth=0.5)

# Display the plot
plt.show()
