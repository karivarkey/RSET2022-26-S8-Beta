from gpiozero import DigitalOutputDevice
from time import sleep

# Pump GPIO setup
pump = DigitalOutputDevice(
    13,                 # GPIO pin
    active_high=True,
    initial_value=False
)

def run_pump(duration_seconds=10):
    """
    Turn pump ON for duration_seconds, then OFF.
    """
    print("[PUMP] Pump ON")
    pump.on()
    sleep(duration_seconds)
    pump.off()
    print("[PUMP] Pump OFF")