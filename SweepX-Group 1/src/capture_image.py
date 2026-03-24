import subprocess
from pathlib import Path
from datetime import datetime
import time

TEMP_DIR = Path.home() / "sweeper" / "temp"

NUM_IMAGES = 10

DELAY_BETWEEN_SHOTS = 1.0

CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
CAPTURE_TIME_MS = 200


def capture_single_image():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_path = TEMP_DIR / f"capture_{timestamp}.jpg"

    cmd = [
        "libcamera-jpeg",
        "-o", str(image_path),
        "-t", str(CAPTURE_TIME_MS),
        "--width", str(CAPTURE_WIDTH),
        "--height", str(CAPTURE_HEIGHT),
        "-n",  # no preview
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"[OK] Saved: {image_path}")
        return image_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed capture: {e}")
        return None


def capture_multiple(n: int):
    """Takes n pictures with delays between them."""
    print(f"[INFO] Taking {n} pictures...")
    for i in range(n):
        print(f"[INFO] Capturing image {i + 1}/{n}...")
        capture_single_image()
        time.sleep(DELAY_BETWEEN_SHOTS)

    print("[INFO] Done.")