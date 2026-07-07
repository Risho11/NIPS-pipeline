import cv2

cam0 = cv2.VideoCapture(0)

ret, frame = cam0.read()

cv2.imwrite("/var/lib/jupyter/notebooks/2025-07-02/lib/frame.png", frame)