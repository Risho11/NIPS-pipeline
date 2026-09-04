"""Show a live preview from OpenCV camera index 2.

Press q while the preview window is focused to close it.
"""

import cv2


CAMERA_INDEX = 2


def main() -> None:
    camera = cv2.VideoCapture(CAMERA_INDEX)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    if not camera.isOpened():
        raise RuntimeError(f"Unable to open camera index {CAMERA_INDEX}")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError(f"Unable to read from camera index {CAMERA_INDEX}")

            cv2.imshow("Camera 2 - press q to close", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
