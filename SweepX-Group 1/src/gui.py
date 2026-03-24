import serial
import tkinter as tk

# CHANGE THIS to your COM port
PORT = "COM8"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)

root = tk.Tk()
root.title("ESP32 Sensor Monitor")
root.geometry("400x300")

sensor_labels = {}
for i in range(1, 5):
    lbl = tk.Label(root, text=f"Sensor {i}: -- cm", font=("Arial", 14))
    lbl.pack(pady=5)
    sensor_labels[i] = lbl

obstacle_label = tk.Label(root, text="", font=("Arial", 14), fg="red")
obstacle_label.pack(pady=10)


def update_data():
    if ser.in_waiting:
        line = ser.readline().decode(errors='ignore').strip()

        # Parse sensor values
        if "Sensor 1:" in line:
            value = line.split(":")[1].strip()
            sensor_labels[1].config(text=f"Sensor 1: {value} cm")

        if "Sensor 2:" in line:
            value = line.split(":")[1].strip()
            sensor_labels[2].config(text=f"Sensor 2: {value} cm")

        if "Sensor 3:" in line:
            value = line.split(":")[1].strip()
            sensor_labels[3].config(text=f"Sensor 3: {value} cm")

        if "Sensor 4:" in line:
            value = line.split(":")[1].strip()
            sensor_labels[4].config(text=f"Sensor 4: {value} cm")

        if "OBSTACLE DETECTED" in line:
            obstacle_label.config(text=line)
        else:
            obstacle_label.config(text="")

    root.after(50, update_data)


update_data()
root.mainloop()
