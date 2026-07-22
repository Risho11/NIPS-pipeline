# ==================================================
# SECTION: Import Libraries
# ==================================================
import json
import time
import sys
import datetime
sys.path.append("/var/lib/jupyter/notebooks/2026-06-11/lib/")

from arm import Arm
from ot2 import OT2
from chiller import BathChiller
from uno_control import Uno
import url as url
from http.server import BaseHTTPRequestHandler, HTTPServer

import threading

# ==================================================
# SECTION: Variable Declaration
# ==================================================

# variables to simulate actions
simulate_compression_tests = True
take_picture = False

# set number of tests we want
tests = ["coupon test 1", "coupon test 2", "coupon test 3", "coupon test 4"]

# mutexes for the different machines, since they can be doing only 1 task at a time
opentronsLock = threading.Lock()
armLock = threading.Lock()
compressionTesterLock = threading.Lock() # this is for running the compression tester AND for placing coupons onto the compression tester/intermediate platform
chillerLock = threading.Lock() # this is for setting the temperature of the chiller AND for placing coupons into the bath
opentronsStandLock = threading.Lock() # make sure two processes aren't trying to do stuff here at the same time, as in trying to drop drop solution there with the opentrons while the arm is trying to place a new coupon or something
cameraLock = threading.Lock() # make sure two processing aren't fighting over the camera box, as in trying to open the box while another process is trying to take a picture
parametersLock = threading.Lock() # make sure two processes aren't trying to save to the parameters.json file at the same time

# load robot parameters from .json
with open('robot.json') as robot_file:
    robot = json.load(robot_file)

coupons = robot["coupons"] # number of clean coupons in the stack
rings = robot["rings"] # number of rings on the stand
discard = robot["discard"] # number of dirty coupons/rings in the discard stack
tip_index = robot["tip_index"] # current index of the tip rack in the opentrons, starting from 0
heater_well_index = robot["heater_well_index"] # current index of the heater block in the opentrons, starting from 0
opentrons_stand_status = robot["opentrons_stand_status"] # "empty", "clean" or "dirty"
camera_box_open = robot["camera_box_open"] # True if the box is open and false if it's closed

runProcess = None # no current process

# ==================================================
# SECTION: Error Check
# ==================================================

# make sure we have at least 1 ring and 1 coupon
errors = ""
if coupons <= 0:
    errors += "There must be at least 1 coupon in the pile. \n"
if rings <= 0:
    errors += "There must be at least 1 ring on the stand. \n"
# make sure opentrons stand is empty
if opentrons_stand_status != "empty":
    errors += "Opentrons stand must be empty. \n"
# must have enough tips
if tip_index > 96 - 3:
    errors += "There must be at least 3 available tips \n"
# must have empty wells
if heater_well_index >= 24:
    errors += "There must be at least 1 clean heater well. \n"
# print errors
if errors != "":
    print(errors)
    print("Please fix errors and update robot.json accordingly. Exiting.")
    exit()

# ==================================================
# SECTION: Equipment Initalization
# ==================================================

# initialize Arm, Arduino (CompressionTester & NitrogenBlower), Chiller, & Opentrons
chiller = BathChiller()
arduino = Uno() # compression tester should not be connected to arduino while initializing, may accidentally start test
xArm = Arm(coupons = coupons, rings = rings, discards = discard, camera_box_open = camera_box_open)
opentrons = OT2(tip_index = tip_index, heater = True, heater_well_index = heater_well_index)

opentrons._drop() # drop tip if we have one
xArm.open_gripper()

# ==================================================
# SECTION: User Comfirmation
# ==================================================

# prompt user to make sure machine is the state specified by the file
print("Please confirm that the machine is in the following state:\n")
print("Coupons in Pile: " + str(coupons))
print("Rings on Stand: " + str(rings))
print("Assemblies in Discard Pile: " + str(discard))
print("The first tip in the tip rack is in well no. " + str(tip_index + 1))
print("The first clean well in the heater is well no. " + str(heater_well_index + 1))
print("All coupon stands (opentrons, bath, compression tester) are empty")
print("The knife is dry and on the knife stand")
print("The N2 cap is on the stand")
print("All baths (knife cleaning bath, nips bath, chiller bath) are filled with water")
if simulate_compression_tests:
    print("Compression tests will be simulated.")
answer = input("is this correct? (Y/N): ")

if answer != "Y" and answer != "y":
    print("Recieved negative answer.")
    print("Please update file robot.json to reflect current state, or change state of the robot.")
    print("Exiting.")
    exit()
else:
    print("Recieved positive answer, continuing.")


# ==================================================
# SECTION: Log inialization and server definition
# ==================================================

# server definition
class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_body_bytes = self.rfile.read(content_length)
        post_body_str = post_body_bytes.decode('utf-8')
        parameters = json.loads(post_body_str)
        response = f"Creating Membrane with following parameters: {post_body_str}"
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
        print("Recievied request for membrane with following parameters: ")
        print(parameters)
        global runProcess
        runProcess = threading.Thread(target=run_test, args=(parameters, ))
        runProcess.start()

# log capture defintion
class _LogCapture:
    def __init__(self, stream):
        self._stream = stream
        self.lines = []
    def write(self, msg):
        self._stream.write(msg)
        if msg.strip():
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.lines.append(f"[{ts}] {msg.rstrip()}")
    def flush(self):
        self._stream.flush()
    def __getattr__(self, name):
        return getattr(self._stream, name)

# log inialization
_capture = _LogCapture(sys.__stdout__)
sys.stdout = _capture
sys.stderr = _LogCapture(sys.__stderr__)


# ==================================================
# SECTION: Helper Functions
# ==================================================

# helper function to save the current state of the machine into the file, as we will save many times during the protocol incase the protocol is interrupted
def save_parameters():
    parametersLock.acquire()
    # serialize robot parameters back into .json
    robot["coupons"] = xArm.coupons
    robot["rings"] = xArm.rings
    robot["discard"] = xArm.discards
    robot["tip_index"] = opentrons.tip_index
    robot["heater_well_index"] = opentrons.heater_well_index
    robot["opentrons_stand_status"] = globals()["opentrons_stand_status"]
    robot["camera_box_open"] = xArm.camera_box_open

    with open('robot.json', "w") as robot_file:
        json.dump(robot, robot_file)
    parametersLock.release()

# load parameters from robot.json file
def load_parameters():
    parametersLock.acquire()
    
    # load robot parameters from .json
    with open('robot.json') as robot_file:
        robot = json.load(robot_file)
    
    # update parameters from the file while the program is running
    # this way we can for example add new coupons and rings without shutting down the server
    xArm.coupons = robot["coupons"]
    xArm.rings = robot["rings"]
    xArm.discards = robot["discard"]
    opentrons.tip_index = robot["tip_index"]
    opentrons.heater_well_index = robot["heater_well_index"] 
    globals()["opentrons_stand_status"] = robot["opentrons_stand_status"]
    xArm.camera_box_open = robot["camera_box_open"]

    parametersLock.release()

# perform zero tests on coupon
def zero_and_place_coupon():
    if globals()["opentrons_stand_status"] != "empty":
        print("Opentrons coupon platform should be empty before grabbing a new coupon. Unsure what to do, exiting.")
        sys.exit()
    
    # this whole thing with the loop and the nested if statements feels silly but it should avoid hold and wait to avoid deadlock and keeps things mostly efficient
    # the idea is that we try to acquire each lock, but if we can't acquire it immediately, then we should release all of our current locks and then try again
    # this same pattern gets used several times in this file, basically whenver we need to acquire 2 or more locks at a time
    done = False
    while not done:
        if armLock.acquire(False):
            if opentronsStandLock.acquire(False):
                if compressionTesterLock.acquire(False):
                    xArm.pick_up_coupon()
                    save_parameters() # number of coupons has changed, update file
                    xArm.put_down("coupon angled tester", pitch = False)

                    # take coupon to compression tester
                    xArm.prep_coupon_test()

                    safe = True
                    recent = True
                    for test in tests:
                        if safe and recent:
                            xArm.put_down(test)
                            armLock.release() # we can release the arm while we run the test, it's not time sensitive
                            safe = not arduino.run_test()

                        if safe:
                            time.sleep(5) # make sure newton software has finished processing the test into a .csv file
                            # use the data from the laptop to make sure the test finished correctly
                            data = url.get_compressiontester_status()
                            safe = data["safe"]
                            recent = (time.time() - data["time"]) < 30
                            print("Safe: " + str(safe))
                            print("Recent: " + str(recent))
                            print("Time: " + str(time.time()))
                            print("mTime: " + str(data["time"]))

                        if safe and recent:
                            armLock.acquire() # acquire the arm again to pick up the coupon
                            xArm.pick_up(test)

                    # if we aren't safe or recent here, that means we must have released the arm and need to acquire it again
                    if not safe:
                        print("Compression tester is unsafe! exiting...")
                        armLock.acquire()
                        xArm.immigrate("middle")
                        sys.exit()
                    elif not recent:
                        print("Compression test is out of date, tester could still be running. Unsure. exiting...")
                        armLock.acquire()
                        xArm.immigrate("middle")
                        sys.exit()

                    # but if we are safe and recent, then we must still have the arm locked so we don't need to acquire it again
                    # put coupon back on intermediate platform
                    xArm.unprep_coupon_test()
                    xArm.pick_up("coupon angled tester")
                    compressionTesterLock.release()
                    
                    done = True
                    
                if done:
                    # finish everything that doesn't still need the compression tester
                    # there's no real reason not do to this in the previous block since there's nothing that would need the compressiontester but not the arm but this is technically what you should do
                    xArm.put_down("coupon angled opentrons", pitch = False)
                    globals()["opentrons_stand_status"] = "clean"
                    save_parameters()
                    # move arm out of the way
                    xArm.immigrate("middle")
                opentronsStandLock.release()
            armLock.release()

# do the compression tests
def run_compression_tests():
    # assume coupon is on tester coupon stand
    # assume armLock is already acquired 

    done = False
    while not done:
        if compressionTesterLock.acquire(False):        
            # take coupon to compression tester
            xArm.prep_coupon_test()
            safe = True
            recent = True

            for test in tests:
                if safe and recent:
                    xArm.put_down(test)
                    armLock.release() # nothing here needs a deadline anymore so we're free to release the arm
                    safe = not arduino.run_test()
                if safe:
                    time.sleep(5) # make sure newton software has finished processing the test into a .csv file
                    # use the data from the laptop to make sure the test finished correctly
                    data = url.get_compressiontester_status()
                    safe = data["safe"]
                    recent = (time.time() - data["time"]) < 30
                    print("Safe: " + str(safe))
                    print("Recent: " + str(recent))
                    print("Time: " + str(time.time()))
                    print("mTime: " + str(data["time"]))
                if safe and recent:
                    armLock.acquire()
                    xArm.pick_up(test)

            if not safe:
                print("Compression tester is unsafe! exiting...")
                armLock.acquire()
                xArm.immigrate("middle")
                sys.exit()
            elif not recent:
                print("Compression test is out of date, tester could still be running. Unsure. exiting...")
                armLock.acquire()
                xArm.immigrate("middle")
                sys.exit()
                    
            # put coupon back on intermediate platform
            xArm.unprep_coupon_test()

            # release lock, finish program  
            compressionTesterLock.release()
            done = True


# clean the knife after a given delay
def delayed_knife_cleaning(delay = 0):
    time.sleep(delay)
    
    armLock.acquire()
    # go clean the knife
    print("Cleaning knife")
    xArm.clean_knife(brush_cycles = 5, dry_cycles = 15)
    xArm.immigrate("middle")
    armLock.release()
    print("Knife cleaning finished.")

# simulation zero tests if compression tester is not working
def simulate_zero_and_place_coupon():
    armLock.acquire()
    
    xArm.pick_up_coupon()
    save_parameters()
    xArm.put_down("coupon angled tester", pitch = False)

    # take coupon to compression tester
    xArm.prep_coupon_test()
    # move coupon to the test points, and then run the zero tests (3 tests where the membrane will be)
    for test in tests:
        xArm.put_down(test)
        xArm.pick_up(test)

    xArm.unprep_coupon_test()
    xArm.pick_up("coupon angled tester")
    xArm.put_down("coupon angled opentrons", pitch = False)

    # move arm out of the way
    xArm.immigrate("middle")
    armLock.release()



# ============================================================================
# SECTION: Main Function
# ============================================================================

def run_test(param = None):
    
    # ==================================================
    # SECTION: Load Variables
    # ==================================================

    # load parameter file
    if param == None:
        # load parameters from .json file
        with open('parameters.json') as file:
            parameters = json.load(file)
    else:
        parameters = param
    load_parameters()

    # variable declaration
    mixing_temp = parameters["mixing_temp"]
    bath_temp = parameters["bath_temp"]
    pullcast_speed = parameters["pullcast_speed"]
    nitrogen = parameters["nitrogen"]
    coupon_to_bath_wait_time = parameters["coupon_to_bath_wait_time"]
    nips_bath_time = parameters["nips_bath_wait_time"]
    desired_weight_percent = parameters["polymer_wt"]
    desired_additive_percent = parameters["additive_wt"]
    total_vol = 1000 # volume is always 1000

    # if metadata exists, update OT2 variables
    if "stock_metadata" in parameters:
        opentrons.update_metadata(parameters["stock_metadata"])

    # if weight percent is higher than what we have, exit
    if desired_weight_percent > opentrons.get_stock_weight_percent():
        print("Desired weight percent is too high. Exiting.")
        exit()
    
    # check if additive percentage is too high, exit
    if desired_additive_percent > opentrons.get_additive_percent():
        print("Desired additive percent is too high. Exiting.")
        exit()

    # ==================================================
    # SECTION: Begin Background Tasks
    # ==================================================

    # Background task 1: start chilling the chiller
    chiller_process = threading.Thread(target=chiller.go_to_temperature, args=(bath_temp, ))
    chiller_process.start()
    print("Bath chilling process started.")

    # Background task 2: take a clean coupon, run the three zero tests on it, then place it into the opentrons
    if simulate_compression_tests:
        place_coupon_process = threading.Thread(target = simulate_zero_and_place_coupon)
        print("Simulating zero tests.")
    else:
        place_coupon_process = threading.Thread(target = zero_and_place_coupon)
    place_coupon_process.start()
    print("Beginning zero tests on coupons.")
    
    # ==================================================
    # SECTION: Prepare membrane solution
    # ==================================================

    # Foreground task: mix/asperate the correct concentration of solution
    opentronsLock.acquire()
    print("Opentrons process started.")

    # prepare membrane solution
    opentrons.prepare_membrane_solution(total_vol, desired_weight_percent, desired_additive_percent, mixing_temp)
    
    # make sure the chiller is at temp and that the clean (and zeroed) coupon has been placed before continuing
    chiller_process.join()
    place_coupon_process.join()

    # 0 background tasks now
    print("Joined both subprocesses.")
    
    # ==================================================
    # SECTION: Dispense and Pullcast
    # ==================================================

    # dispense solution on coupon
    opentronsStandLock.acquire()
    opentrons.prep_pullcast_dispense(total_vol)
    globals()["opentrons_stand_status"] = "dirty"
    save_parameters()

    # drop opentrons tip
    dropProcess = threading.Thread(target = opentrons._drop)
    dropProcess.start()
    
    # pullcast membrane
    armLock.acquire()
    xArm.pullcast(speed = pullcast_speed)
    print("Pullcast complete.")

    # don't need the opentrons anymore, just the stand
    dropProcess.join()
    opentronsLock.release()

    # set up knife cleaning in background, will begin when arm is released
    knife_cleaning_process = threading.Thread(target=delayed_knife_cleaning, args=(300, ))
    knife_cleaning_process.start()
    
    # new background task 1: clean the knife
    # wait at least 5 minutes before trying to clean the knife (currently we won't release the arm until after we place the rings but hey maybe in the future we'll figure out some premption or something)
    # we will join this process at the end of the protocol most likely since we don't actually care about the knife it's very low priority as long as it's clean for the next run

    # ==================================================
    # SECTION: Membrane formation
    # ==================================================

    # foreground task: do NIPS stuff, coupon will sit on opentrons stand
    if nitrogen:
        arduino.start_blow()
        print("Nitrogen on.")
        xArm.put_cap(hover_time = coupon_to_bath_wait_time)
        arduino.stop_blow()
        print("Nitrogen off.")
    else:
        time.sleep(coupon_to_bath_wait_time)

    # place coupon in water bath
    xArm.put_coupon_bath()
    globals()["opentrons_stand_status"] = "empty"
    save_parameters()
    opentronsStandLock.release() # we aren't using the opentrons stand anymore
    
    # background task 2: start a timer for nips in the background, since this timer should start as close to when the coupon is placed in the water, rather than after we put the cap away and add a ring
    nips_timer_process = threading.Thread(target=time.sleep, args=(nips_bath_time, ))
    nips_timer_process.start()
    print(f"Membrane sitting in bath for {nips_bath_time} seconds.")

    # put away nitrogen cap (if enabled)
    if nitrogen:
        xArm.pick_up("cap bath")
        xArm.put_down("cap stand")
        print("Nitrogen cap has been put away.")

    # place ring on coupon
    xArm.pick_up_ring()
    save_parameters() # number of rings has changed, update file
    xArm.put_down("ring bath")
    print("Ring has been placed on the coupon.")

    # wait until the nips timer is up
    armLock.release()
    nips_timer_process.join()

    # ==================================================
    # SECTION: Iniatial Picture
    # ==================================================

    # acquire thread locks
    armLock.acquire()
    cameraLock.acquire()

    # move coupon to the camera to take the pre-test picture
    xArm.pick_up("coupon bath", pitch = False)
    xArm.hover_bath(wait_time = 600) # submerge in a water bath
    xArm.put_down("coupon camera tester", pitch = False)
    xArm.currentZone = "middle" # speed up process
    xArm.close_camera_box()

    if(take_picture):
        time.sleep(2) # make sure the camera has time to adjust to the lighting and everything
        url.take_snapshot()
        print("Initial membrane picture taken.")
    
    # ==================================================
    # SECTION: Compression tests
    # ==================================================

    # move coupon to compression tester
    xArm.open_camera_box()
    xArm.currentZone = "tester" # speeds up process
    xArm.pick_up("coupon camera tester", pitch = False)
    xArm.put_down("coupon angled tester", pitch = False)
    cameraLock.release() # don't need the camera box right now

    # simulated tests
    if simulate_compression_tests:            
        # take coupon to compression tester
        compressionTesterLock.acquire()
        xArm.prep_coupon_test()
            
        print("Simulating compression tests.")
        for test in tests:
            xArm.put_down(test)
            xArm.pick_up(test)

        # put coupon back on intermediate platform
        xArm.unprep_coupon_test()
        compressionTesterLock.release()
            
    # perform real compression tests
    else:                
        run_compression_tests()

    # ==================================================
    # SECTION: Final Picture
    # ==================================================

    # get coupon from tester stand    
    cameraLock.acquire()
    xArm.open_camera_box()
    xArm.pick_up("coupon angled tester", pitch = False)
                
    # go put the coupon in the box for the post-test picture
    xArm.put_down("coupon camera tester", pitch = False)
    xArm.currentZone = "middle"
    xArm.close_camera_box()

    if(take_picture):
        time.sleep(2) # give time for camera to adjust to lighting
        url.take_snapshot()
        print("Final membrane picture taken.")
    
    # ==================================================
    # SECTION: Clean up
    # ==================================================

    # put coupon in discard pile
    xArm.open_camera_box()
    xArm.currentZone = "tester" # speeds up process
    xArm.pick_up("coupon camera tester", pitch = False)
    xArm.discard(pitch = False)

    # save parameters and release camera lock
    cameraLock.release()
    save_parameters() 
    print("Coupon successfully discarded.")

    # ensure knife is clean
    armLock.release()              
    knife_cleaning_process.join()  
    armLock.acquire()               

    # dry compression tester, acquire locks
    compressionTesterLock.acquire()
    xArm.dry_tester()  
    compressionTesterLock.release()

    # turn off chiller, save electricity
    chiller.turn_off()

    # always end in middle, as next run will assume we're in the middle
    xArm.immigrate("middle")
    armLock.release()
    
    # finish
    print("Done")
    parameters["air_data"] = arduino.read_temp_humidity()
    url.start_processing(parameters, protocol_log=_capture.lines.copy()) # tell the pc that the test is done so it can go process the files
    _capture.lines.clear()  # reset log buffer for next run



# ==================================================
# SECTION: Server inialization
# ==================================================  

# set up server, class definition at top of the document
if __name__ == '__main__':
    server = HTTPServer(("169.254.46.48", 8000), RequestHandler)
    server.serve_forever()
