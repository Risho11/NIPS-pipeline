# import libraries
import json
import time
import sys
sys.path.append("/var/lib/jupyter/notebooks/2026-06-11/lib/")
from arm import Arm

import threading

# mutexes for the different machines, since they can be doing only 1 task at a time
opentronsLock = threading.Lock()
armLock = threading.Lock()
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

# make sure we have at least 1 ring and 1 coupon
errors = ""
if coupons <= 0:
    errors += "There must be at least 1 coupon in the pile. \n"
if rings <= 0:
    errors += "There must be at least 1 ring on the stand. \n"
if opentrons_stand_status != "empty":
    errors += "Opentrons stand must be empty. \n"
if tip_index >= 127:
    errors += "There must be at least 2 available tips \n"
if heater_well_index >= 64:
    errors += "There must be at least 1 clean heater well. \n"
if errors != "":
    print(errors)
    print("Please fix errors and update robot.json accordingly. Exiting.")
    exit()

xArm = Arm(coupons = coupons, rings = rings, discards = discard, camera_box_open = camera_box_open)

xArm.open_gripper()

# prompt user to make sure machine is the state specified by the file
print("Please confirm that the machine is in the following state:\n")
print("Coupons in Pile: " + str(coupons))
print("Rings on Stand: " + str(rings))
print("Assemblies in Discard Pile: " + str(discard))
print("All coupon stands (opentrons, bath, compression tester) are empty")
print("The knife is dry and on the knife stand")
print("The N2 cap is on the stand")
print("All baths (knife cleaning bath, nips bath, chiller bath) are filled with water")
answer = input("is this correct? (Y/N)")

if answer != "Y" and answer != "y":
    print("Recieved negative answer.")
    print("Please update file robot.json to reflect current state, or change state of the robot.")
    print("Exiting.")
    exit()
else:
    print("Recieved positive answer, continuing.")

# helper function to save the current state of the machine into the file, as we will save many times during the protocol incase the protocol is interrupted
def save_parameters():
    parametersLock.acquire()
    # serialize robot parameters back into .json
    robot["coupons"] = xArm.coupons
    robot["rings"] = xArm.rings
    robot["discard"] = xArm.discards
    #robot["tip_index"] = opentrons.tip_index
    #robot["heater_well_index"] = opentrons.heater_well_index
    robot["opentrons_stand_status"] = globals()["opentrons_stand_status"]
    robot["camera_box_open"] = xArm.camera_box_open

    with open('robot.json', "w") as robot_file:
        json.dump(robot, robot_file)
    parametersLock.release()

# load parameters from .json file
with open('parameters.json') as file:
    parameters = json.load(file)
    
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
    #opentrons.tip_index = robot["tip_index"]
    #opentrons.heater_well_index = robot["heater_well_index"] 
    #globals()["opentrons_stand_status"] = robot["opentrons_stand_status"]
    xArm.camera_box_open = robot["camera_box_open"]
    parametersLock.release()

# test parameters
nitrogen = False
test_clean = False
nitrogen_cap_tests = 0
#tests = ["coupon test 1"]
tests = ["coupon test 1", "coupon test 2", "coupon test 3", "coupon test 4"]
pullcast_enable = True

armLock = threading.Lock()
armLock.acquire()
print("1")
armLock.release()
print("2")
armLock.release()
print("3")

if test_clean:
    xArm.clean_knife()
    #xArm.clean_knife(brush_cycles = 5, dry_cycles = 15)

for i in range(nitrogen_cap_tests):
    # manually place coupon on stand
    xArm.put_cap(hover_time = 2)
    xArm.put_coupon_bath()
    xArm.pick_up("cap bath")
    xArm.put_down("cap stand")
    xArm.pick_up("coupon bath")
    xArm.currentZone = "opentrons"
    xArm.put_down("coupon angled opentrons", pitch = False)

#xArm.dry_tester(squeegee_cycles = 2, middle = False)
    
while robot["coupons"] > 9:
    # place new coupon
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

    if pullcast_enable:
        xArm.pullcast(speed = parameters["pullcast_speed"])
    if nitrogen:
        xArm.put_cap(hover_time = 5)
    
    # move coupon to bath
    xArm.put_coupon_bath()
    if nitrogen:
        xArm.pick_up("cap bath")
        xArm.put_down("cap stand")
    xArm.pick_up_ring()
    save_parameters()
    xArm.put_down("ring bath")

    # take coupon from bath to camera
    xArm.open_camera_box()
    #xArm.pick_up("coupon bath", pitch = False, speed = 50)
    xArm.pick_up("coupon bath", pitch = False)
    xArm.immigrate("middle", pitch = False)
    xArm.hover_bath(wait_time = 10)
    xArm.put_down("coupon camera tester", pitch = False)
    xArm.currentZone = "middle"
    xArm.close_camera_box()
    
    # take from camera to tester
    xArm.open_camera_box()
    xArm.currentZone = "tester"
    xArm.pick_up("coupon camera tester", pitch = False)
    xArm.put_down("coupon angled tester", pitch = False)

    # take coupon to compression tester
    xArm.prep_coupon_test()

    for test in tests:
        xArm.put_down(test)
        xArm.pick_up(test)

    # put coupon back on intermediate platform
    xArm.unprep_coupon_test()
    
    # simulate picture taking again
    xArm.open_camera_box()
    xArm.pick_up("coupon angled tester", pitch = False)
    xArm.put_down("coupon camera tester", pitch = False)
    xArm.currentZone = "middle"
    xArm.close_camera_box()
    xArm.open_camera_box()
    xArm.currentZone = "tester"

    # put coupon in discard pile
    xArm.pick_up("coupon camera tester")
    xArm.discard()
    save_parameters() # number of assemblies in discard pile has changed, update file

    # simulate cleaning knife
    if pullcast_enable:
        xArm.clean_knife()
    
    # dry testing platform
    xArm.dry_tester()

# return to home position
xArm.open_gripper()
xArm.immigrate("middle")
