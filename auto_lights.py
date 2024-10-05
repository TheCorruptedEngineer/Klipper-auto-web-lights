import requests
import time
import threading
import socket

# Set the Moonraker API URL
url = "http://192.168.1.31:80/printer/objects/query?heater_bed&extruder"

# Set the URL for controlling lights
light_url = "http://192.168.1.17/"

# Global variable to manage auto mode
auto = True


# Function to set light color
def set_light_color(red, green, blue):
    try:
        requests.get(f"{light_url}?red={red}&green={green}&blue={blue}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to set light color: {e}")


# Function to handle incoming socket connections
def socket_listener():
    global auto
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 12345))  # Listen on all interfaces on port 12345
    server_socket.listen(1)
    print("Listening for commands on port 12345...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        command = client_socket.recv(1024).decode('utf-8').strip()

        if command.lower() == "quit":
            exit()

        elif command.lower() == "auto":
            auto = True  # Enable auto mode
            print("Auto mode enabled.")
        elif command.lower().startswith("rgb "):
            # Try to parse RGB values from the command
            try:
                rgb_values = list(map(int, command[4:].split(',')))  # Skip the "rgb " prefix
                if len(rgb_values) == 3:
                    set_light_color(*rgb_values)
                    print(f"Lights set to RGB: {rgb_values}")
                    auto = False  # Disable auto mode
                    print("Auto mode Disabled")
                else:
                    print("Invalid RGB command. Use format: rgb R,G,B")
            except ValueError:
                print(f"Invalid RGB command format: {command}")
        else:
            print(f"Unknown command: {command}")

        client_socket.close()


# Initialize variables for tracking previous temperature
prev_extruder_temp = None
prev_bed_temp = None

# Define the temperature threshold for stability
temperature_threshold = 0.5

# Define the initial delay and the maximum delay for retries
initial_delay = 10  # seconds
max_delay = 100  # seconds (10 minutes)
retry_delay = initial_delay

# Start the socket listener in a separate thread
listener_thread = threading.Thread(target=socket_listener, daemon=True)
listener_thread.start()

try:
    # Loop until either the extruder or bed temperature reaches 200°C or 85°C respectively
    while True:
        if auto:
            try:
                # Send a request to Moonraker API
                response = requests.get(url)
                response.raise_for_status()  # Check for HTTP request errors

                # Reset retry delay after a successful request
                retry_delay = initial_delay

                # Parse the JSON response
                data = response.json()

                # Extract extruder and bed temperatures
                extruder_temp = data['result']['status']['extruder']['temperature']
                bed_temp = data['result']['status']['heater_bed']['temperature']

                # Print the current temperatures
                print(f"Current Extruder Temperature: {extruder_temp}°C")
                print(f"Current Bed Temperature: {bed_temp}°C")

                # Only adjust lights if auto mode is enabled
                # Compare current temperatures with previous to detect changes
                if prev_extruder_temp is not None and prev_bed_temp is not None:
                    extruder_change = abs(extruder_temp - prev_extruder_temp)
                    bed_change = abs(bed_temp - prev_bed_temp)

                    if extruder_change > temperature_threshold or bed_change > temperature_threshold:
                        if extruder_temp > prev_extruder_temp or bed_temp > prev_bed_temp:
                            # Temperature is rising, set lights to red
                            set_light_color(255, 0, 0)
                            print("Temperature is rising, lights set to red.")
                        elif extruder_temp < prev_extruder_temp or bed_temp < prev_bed_temp:
                            # Temperature is falling, set lights to blue
                            set_light_color(0, 0, 255)
                            print("Temperature is falling, lights set to blue.")
                    else:
                        # Temperature is stable (within threshold), set lights to white
                        set_light_color(255, 255, 255)
                        print("Temperature is stable, lights set to white.")

                # Update previous temperature values for next iteration
                prev_extruder_temp = extruder_temp
                prev_bed_temp = bed_temp

                # Wait before checking again (e.g., every 10 seconds)
                time.sleep(10)

            except requests.exceptions.RequestException as e:
                # Print the error
                print(f"Error: {e}")

                # Increase the delay (exponential backoff)
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

                # Double the retry delay for the next attempt, but cap it at max_delay
                retry_delay = min(retry_delay * 2, max_delay)
        else:
            time.sleep(20)

except KeyboardInterrupt:
    print("Script interrupted.")
