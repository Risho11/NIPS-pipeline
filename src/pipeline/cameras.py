# Camera stuff
import cv2
import numpy

numCam = 4

cam = [None] * numCam
ret = [None] * numCam
frame = [None] * numCam

height = 1080
width = 1920

for i in range(numCam):
    cam[i] = cv2.VideoCapture(i)
    cam[i].set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cam[i].set(cv2.CAP_PROP_FRAME_HEIGHT, height)

cv2.namedWindow("Frame", cv2.WINDOW_FREERATIO)

def showCameras():
    while True:
        for i in range(numCam):
            ret[i], frame[i] = cam[i].read()
            if ret[i] == False:
                frame[i] = numpy.zeros((height, width, 3), numpy.uint8)
            elif i in (0, 1):
                frame[i] = cv2.rotate(frame[i], cv2.ROTATE_180)
#        print(ret)

        topFrame = cv2.hconcat(frame[0:2])
        bottomFrame = cv2.hconcat(frame[2:4])

        outFrame = cv2.vconcat([topFrame, bottomFrame])


        cv2.imshow("Frame", outFrame)
        if cv2.waitKey(1) == ord('q'):
            break

showCameras()
