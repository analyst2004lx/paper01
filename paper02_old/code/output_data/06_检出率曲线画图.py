import matplotlib.pyplot as plt

# Data from the table
proportion_attack_traffic = [2.5, 7.5, 10.0, 13.0, 15.0, 17.5, 20.0, 22.5, 25.0, 28.0, 30.0, 32.5, 35.0, 37.5, 40.0, 43.0, 45.0, 47.5, 50.0]
detection_rate_flow = [0.0, 0.0, 0.0, 0.0, 0.0, 4.6, 4.9, 4.67, 11.5, 30.8, 40.5, 50.9, 67.3, 73.2, 77.32, 92.5, 94.0, 94.3, 94.6]
detection_rate_new = [97.5, 97.5, 97.5, 97.5, 95.3, 93.5, 92.6, 90.0, 88.6, 82.2, 82.2, 80.7, 80.1, 79.3, 78.6, 78.1, 77.9, 77.82, 77.8]

# Colors from the provided image colors
flow_measurement_color = '#c24d4d'  # Red color for flow measurement method
new_method_color = '#92b774'        # Green color for the new method

# Create the plot
plt.figure(figsize=(10, 6))

# Plot the first line (flow measurement method)
plt.plot(proportion_attack_traffic, detection_rate_flow, label='Detection Rate (flow measurement method)', marker='s', color=flow_measurement_color)
# Plot the second line (new method)
plt.plot(proportion_attack_traffic, detection_rate_new, label='Detection Rate (new method)', marker='o', color=new_method_color)

# Set axis labels and title
plt.xlabel('Proportion of Attack Traffic (%)')
plt.ylabel('Detection Rate (%)')
plt.title('Detection Rate Comparison between Flow Measurement Method and New Method')

# Add legend
plt.legend()

# Show the grid for better readability
plt.grid(True, linestyle='--', linewidth=0.5)

# Display the plot
plt.show()