# !/usr/bin/env python3

import time
from pathlib import Path
from dirt_model import classify_all_in_temp
from time import sleep
from capture_image import capture_multiple, TEMP_DIR
from aurdino_control import run_motor
from pump import run_pump

# Delete images older than N minutes from TEMP_DIR
# def delete_old_images(max_age_minutes=5):
#     now = time.time()
#     max_age_seconds = max_age_minutes * 60

#     temp_dir = Path(TEMP_DIR)
#     if not temp_dir.exists():
#         return

#     for file in temp_dir.glob("*.jpg"):
#         try:
#             file_age = now - file.stat().st_mtime
#             if file_age > max_age_seconds:
#                 file.unlink()
#                 print(f"[CLEANUP] Deleted old file: {file}")
#         except Exception as e:
#             print(f"[CLEANUP ERROR] Could not delete {file}: {e}")


def main():
    # Change this number whenever you want to take more/less images
    NUM_SHOTS = 5

    print("[MAIN] Starting image capture...")
    capture_multiple(NUM_SHOTS)

    # print("[MAIN] Cleaning up old images (older than 5 minutes)...")
    # delete_old_images(max_age_minutes=5)
    # sleep(3)

    print("[MAIN] Running dirt model on captured images...")
    results = classify_all_in_temp()

    # added logic (comments untouched)
    any_dirty = any(is_dirty for _, is_dirty, _ in results) if results else False

    print("Starting pump...")
    run_pump(duration_seconds=10)
    print("Pump finished.")

    if any_dirty:
        print("[MAIN] Dirt detected - running motor")
        run_motor(duration_seconds=5)
    else:
        print("[MAIN] Panel clean - motor not activated")

    print("[MAIN] Done.")


if __name__ == "__main__":
    main()