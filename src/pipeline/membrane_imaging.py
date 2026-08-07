"""membrane_imaging.py — image_processing branch.

Ported from Image Processing/Main Code.ipynb. That notebook was built specifically to find a
probe-placement spot for the compression tester (its final "test point" stage). The general
membrane-quality analysis underneath (brightness-difference threshold -> denoise -> uniform
region detection) isn't inherently compression-tester-specific, so it's exposed on its own via
analyze_membrane(); find_probe_test_point() is kept as a separate, clearly compression-tester-
specific step on top of it.

Two algorithms from the notebook were dropped: the vectorized integral-image denoiser (notebook's
own note: results didn't match the loop version, never fully debugged) and 2D convolution
(notebook's own note: can take tens of minutes, not recommended). The loop-based integral-image
approach kept here is the one the notebook's own results (PPT) were based on.
"""
import re
from pathlib import Path

import cv2
import numpy as np

#so this approach kinda sucks if the image is out of focus so
#if this is true dont do the membrane thingy. like just don't run any of the math integral stuff functions.
SEND_RAW_IMAGE = True

def generate_padding(image, pad_width=1, pad_value=0):
    return np.pad(image, ((pad_width, pad_width), (pad_width, pad_width)), "constant",
                  constant_values=(pad_value,))


def calculate_integral_image(image):
    return np.cumsum(np.cumsum(image, axis=0), axis=1)


def brightness_difference(image, threshold_difference=4):
    """Vectorized brightness-difference threshold (notebook cell-7).

    Pixel goes white (255) if brighter than 150 AND its 4-neighbor brightness
    difference stays within threshold_difference; otherwise black (0).
    """
    image = image.astype(np.int16)
    padded = generate_padding(image).astype(np.int16)

    top_diff = np.abs(padded[:-2, 1:-1] - padded[1:-1, 1:-1])
    bot_diff = np.abs(padded[2:, 1:-1] - padded[1:-1, 1:-1])
    left_diff = np.abs(padded[1:-1, :-2] - padded[1:-1, 1:-1])
    right_diff = np.abs(padded[1:-1, 2:] - padded[1:-1, 1:-1])
    max_diff = np.maximum(np.maximum(top_diff, bot_diff), np.maximum(left_diff, right_diff))

    result = image.copy()
    result[image > 150] = 255
    result[image <= 150] = 0
    result[max_diff > threshold_difference] = 0
    return result.astype(np.uint8)


def fast_thresholding(image, kernel_n=9, threshold=0.2):
    """Integral-image denoise: zero out pixels whose kernel_n x kernel_n neighborhood
    has too high a black-pixel ratio."""
    integral_image = calculate_integral_image(image)
    output_image = np.ones_like(image) * 255
    threshold_value = (kernel_n ** 2) * threshold
    border_size = kernel_n // 2

    for y in range(border_size, image.shape[0] - border_size):
        for x in range(border_size, image.shape[1] - border_size):
            total = integral_image[y + border_size, x + border_size]
            total -= integral_image[y + border_size, x - border_size - 1]
            total -= integral_image[y - border_size - 1, x + border_size]
            total += integral_image[y - border_size - 1, x - border_size - 1]
            black_pixel_count = (kernel_n ** 2) - total / 255
            if black_pixel_count > threshold_value:
                output_image[y, x] = 0

    return output_image


def uniform_region_detection(image, kernel_n=301):
    """Mark pixels whose kernel_n x kernel_n neighborhood is fully white (no black
    pixels at all) as 170 ("gray" = uniform/defect-free region)."""
    integral_image = calculate_integral_image(image)
    output_image = image.copy()
    border_size = kernel_n // 2

    for y in range(border_size, image.shape[0] - border_size):
        for x in range(border_size, image.shape[1] - border_size):
            total = integral_image[y + border_size, x + border_size]
            total -= integral_image[y + border_size, x - border_size - 1]
            total -= integral_image[y - border_size - 1, x + border_size]
            total += integral_image[y - border_size - 1, x - border_size - 1]
            black_pixel_count = (kernel_n ** 2) - total / 255
            if black_pixel_count == 0:
                output_image[y, x] = 170

    return output_image


def analyze_membrane(image_path, denoise_kernel_n=9, denoise_threshold=0.2,
                      uniform_kernel_n=301) -> dict:
    """General membrane quality analysis. No compression-tester assumptions."""
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"could not read image: {image_path}")

    diff = brightness_difference(image)
    denoised = fast_thresholding(diff, kernel_n=denoise_kernel_n, threshold=denoise_threshold)
    uniform_map = uniform_region_detection(denoised, kernel_n=uniform_kernel_n)

    return {
        "image_path": str(image_path),
        "uniform_map": uniform_map,
    }

def defect_concentration(uniform_map):
    pass

def find_probe_test_point(uniform_map) -> dict:
    """Compression-tester-specific: largest uniform (value-170) disk in uniform_map
    is where the compression probe should land."""
    if not np.any(uniform_map == 170):
        return {"test_point": None, "safe_radius": 0}

    max_distance = 0
    max_coordinate = (0, 0)
    for i in range(len(uniform_map)):
        for j in range(len(uniform_map[i])):
            if uniform_map[i][j] != 170:
                continue
            try:
                if (uniform_map[i + max_distance][j] and uniform_map[i - max_distance][j]
                        and uniform_map[i][j + max_distance] and uniform_map[i][j - max_distance] == 170):
                    max_coordinate = (i, j)
                    distance = 0
                    while (uniform_map[i + distance][j] and uniform_map[i - distance][j]
                           and uniform_map[i][j + distance] and uniform_map[i][j - distance] == 170):
                        distance += 1
                        max_distance = distance
            except IndexError:
                continue

    return {"test_point": max_coordinate, "safe_radius": max_distance}


def _find_pretest_image(condition_dir: Path) -> Path:
    """Earliest-timestamped jpg in condition_dir — move_and_rename (run_loop.py:124-125)
    copies photos taken before AND after the compression test into the same folder; the
    pre-test photo is the one this analysis should run on."""
    jpgs = list(Path(condition_dir).glob("*.jpg"))
    if not jpgs:
        raise FileNotFoundError(f"no jpg found in {condition_dir}")

    def _timestamp(path):
        match = re.match(r"([\d.]+)", path.stem)
        return float(match.group(1)) if match else path.stat().st_ctime

    return min(jpgs, key=_timestamp)


def run(condition_dir: Path) -> dict:
    """Branch entry point used by master_processing. Reads the jpg(s) already dropped
    into condition_dir by move_and_rename — no new capture step.

    SEND_RAW_IMAGE=True (the default): skip the pixel-math entirely and just return the image
    path, for a vision LLM (membrane_quality_llm.py) to judge qualitatively -- the pixel-math
    approach breaks down on out-of-focus photos. SEND_RAW_IMAGE=False: legacy pixel-math path,
    including find_probe_test_point's compression-probe coordinate picking.
    """
    image_path = _find_pretest_image(Path(condition_dir))
    if SEND_RAW_IMAGE:
        return {"image_path": str(image_path)}
    analysis = analyze_membrane(image_path)
    probe_point = find_probe_test_point(analysis["uniform_map"])
    return {**analysis, **probe_point}
