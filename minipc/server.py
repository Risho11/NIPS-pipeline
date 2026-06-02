from pathlib import Path
import os
import shutil
import csv
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
import sys

sys.path.append(r"C:\Users\opentrons\Documents\auto-membranes\\")
import processing as processing

# helper method, create a folder name using the parameters
def get_filename(params):
    filename = ""
    filename = filename + str(params["weight_percent"]) +"wp-"
    filename = filename + str(params["mixing_temp"]) + "degMix-"
    filename = filename + str(params["bath_temp"]) + "deg-"
    filename = filename + str(params["coupon_to_bath_wait_time"]) + "s-"
    if not params["nitrogen"]:
        filename = filename + "No"
    filename = filename + "N2-"
    filename = filename + str(params["nips_bath_wait_time"]) + "s-"
    return filename

# methods for checking if the compression tester is safe
csvPath = Path(r"C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed")

def get_latest():
    fileList = list(csvPath.glob("**/*.csv"))
    return max(fileList, key=os.path.getctime)

def check_safe(file):
    with open(file) as csvfile:
        reader = csv.reader(csvfile)
        data = list(reader)
        isSafe = float(data[-1][5]) < -6
        return isSafe

def check_time(file):
    return os.path.getmtime(file)

# methods for analyzing the previous compression tests
def get_last_set_img():
    fileList = list(Path(r"C:\Users\opentrons\Documents\auto-membranes\images").glob("*.jpg"))
    fileList.sort(key=os.path.getctime)
    fileList = fileList[-2:] # pre and post compression test image
    return fileList

def get_last_set_csv():
    fileList = list(csvPath.glob("**/*.csv"))
    fileList.sort(key=os.path.getctime)
    fileList = fileList[-6:] # 3 zero tests, 3 membrane tests
    return fileList

# copy the last 6 compression tests and last 2 images to their own folder so they can be processed
def move_and_rename(params):
    # put together the folder name based on the parameters
    paramsString = f"{params["weight_percent"]}-"
    if(params["weight_percent"] != 17):
        paramsString += f"{params["mixing_temp"]}degMix-"
    paramsString += f"{params["bath_temp"]}deg-"
    paramsString += f"{params["coupon_to_bath_wait_time"]}s-"
    if(not params["nitrogen"]):
        paramsString += "No"
    paramsString += "N2-"
    paramsString += f"{params["nips_bath_wait_time"]}s"
    
    # create folder
    directory = r"C:\Users\opentrons\Documents\auto-membranes\compression-test-data\\" + paramsString
    try:
        os.mkdir(directory)
    except FileExistsError:
        print(f"These Parameters: {paramsString} have already been tested before. Using the same folder")
        
    # copy images and csv files
    images = get_last_set_img()
    for i in range(2):
        shutil.copy(images[i], directory)
    
    csvs = get_last_set_csv()
    for i in range(6):
        shutil.copy(csvs[i], directory)
    return

# methods for taking snapshots with the camera
import time
import cv2
cam = cv2.VideoCapture(2) # index may change if the computer restarts or if you unplug cameras, mess around with it if you're seeing the wrong camera
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
if not os.path.isdir("images"):
    os.mkdir("images")
def take_snapshot():
    ret, img = cam.read()
    if ret:
        cv2.imwrite(os.path.join("images", str(time.time())) + ".jpg", img)
    else:
        print("Error: unable to take picture")

class RequestHandler(BaseHTTPRequestHandler):
    imgNum = 0
    def do_GET(self):
        path = urlparse(self.path)
        if path.path == "/compressiontester/status":
            self.send_response(200)
            self.end_headers()
            latest = get_latest()
            safe = check_safe(latest)
            time = check_time(latest)
            self.wfile.write(json.dumps({"safe": safe, "time": time}).encode())
        elif path.path == "/camera/snapshot":
            self.send_response(200)
            self.end_headers()
            take_snapshot()
            self.wfile.write(json.dumps(True).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
    def do_POST(self):
        path = urlparse(self.path)
        if path.path == "/server/process":
            content_length = int(self.headers.get('Content-Length', 0))
            post_body_bytes = self.rfile.read(content_length)
            post_body_str = post_body_bytes.decode('utf-8')
            parameters = json.loads(post_body_str)
            print(f"Latest Compression test had following parameters: {parameters}")
            move_and_rename(parameters)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"true")
            processing.run_master_property_extraction(
                folder_name="compression-test-data",
                data_root=r"C:\Users\opentrons\Documents\auto-membranes",
                output_csv=r"C:\Users\opentrons\Documents\auto-membranes\output.csv",
                strict=True,
                suppress_plots=True,
            )
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

if __name__ == '__main__':
    
    server = HTTPServer(("169.254.230.148", 8000), RequestHandler)
    print("serving @ http://169.254.230.148:8000")
    server.serve_forever()
