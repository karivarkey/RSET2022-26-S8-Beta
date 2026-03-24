#!/usr/bin/env python3
import numpy as np
import cv2
from pathlib import Path
from tflite_runtime.interpreter import Interpreter

from capture_image import TEMP_DIR

# ===== CONFIG =====

# Your TFLite model path
MODEL_PATH = "/home/jacob/sweeper/model/model_int8_20251004_173460.tflite"


def load_interpreter():
    print(f"[MODEL] Loading TFLite model from: {MODEL_PATH}")
    interpreter = Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    return interpreter


def preprocess_image(img, input_shape, input_dtype):
    """Prepare image for TFLite model."""
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    if len(input_shape) != 4:
        raise ValueError(f"Unexpected input shape: {input_shape}")

    # Detect data format: NHWC vs NCHW
    if input_shape[1] == 3:
        # NCHW: (1, 3, H, W)
        target_h = input_shape[2]
        target_w = input_shape[3]
        data_format = "NCHW"
    else:
        # Assume NHWC: (1, H, W, 3)
        target_h = input_shape[1]
        target_w = input_shape[2]
        data_format = "NHWC"

    resized = cv2.resize(img_rgb, (target_w, target_h), interpolation=cv2.INTER_AREA)


    # Match dtype expected by model
    if input_dtype == np.uint8:
        input_data = resized.astype(np.uint8)
    else:
        input_data = resized.astype(np.float32) / 255.0

    if data_format == "NHWC":
        input_data = np.expand_dims(input_data, axis=0)  # (1, H, W, 3)
    else:  # NCHW
        input_data = np.transpose(input_data, (2, 0, 1))  # (3, H, W)
        input_data = np.expand_dims(input_data, axis=0)   # (1, 3, H, W)

    return input_data


def classify_image(image_path, interpreter):
    """
    Run model on a single image.

    Returns:
        is_dirty (bool), prob_dirty (float)
    """
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[MODEL] Could not read image: {image_path}")
        return None, None

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    input_index = input_details[0]['index']
    input_shape = input_details[0]['shape']
    input_dtype = input_details[0]['dtype']

    input_data = preprocess_image(img, input_shape, input_dtype)

    interpreter.set_tensor(input_index, input_data)
    interpreter.invoke()

    output_index = output_details[0]['index']
    output_data = interpreter.get_tensor(output_index)

    # Your rule:
    # prob_dirty < 0.5 = CLEAN (False)
    # prob_dirty >= 0.5 = DIRTY (True)
    prob_dirty = float(np.squeeze(output_data)/100)
    is_dirty = prob_dirty >= 1

    return is_dirty, prob_dirty
def classify_all_in_temp():
    """
    Run the model on all JPGs in TEMP_DIR.

    Returns:
        list of (image_path, is_dirty, prob_dirty)
    """
    temp_dir = Path(TEMP_DIR)
    if not temp_dir.exists():
        print(f"[MODEL] Temp directory not found: {temp_dir}")
        return []

    image_paths = sorted(temp_dir.glob("*.jpg"))
    if not image_paths:
        print(f"[MODEL] No images found in: {temp_dir}")
        return []

    interpreter = load_interpreter()
    results = []

    for image_path in image_paths:
        is_dirty, prob_dirty = classify_image(image_path, interpreter)
        if is_dirty is None:
            continue

        status = "DIRTY" if is_dirty else "CLEAN"
        print(f"[RESULT] {image_path.name}: {status} (prob_dirty={prob_dirty:.3f})")

        results.append((image_path, is_dirty, prob_dirty))

    return results