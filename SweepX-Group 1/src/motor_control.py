from gpiozero import DigitalOutputDevice
from time import sleep

# Motor GPIO setup
motor = DigitalOutputDevice(
    12,                 # GPIO pin
    active_high=True,
    initial_value=False
)

def run_motor(duration_seconds=5):
    """
    Turn motor ON for duration_seconds, then OFF.
    """
    print("[MOTOR] Motor ON")
    motor.on()
    sleep(duration_seconds)
    motor.off()
    print("[MOTOR] Motor OFF")