# ==================================================
# SECTION: Import Libraries
# ==================================================
import json
import time
import sys
import datetime
sys.path.append("/var/lib/jupyter/notebooks/2026-06-11/lib/")

from arm import Arm

import threading

# ==================================================
# SECTION: Variable Declaration
# ==================================================

# variables to simulate actions
take_picture = True

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

def error_check():
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

error_check()
        
# ==================================================
# SECTION: Equipment Initalization
# ==================================================

# initialize Arm
xArm = Arm(coupons = coupons, rings = rings, discards = discard, camera_box_open = camera_box_open)
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

answer = input("is this correct? (Y/N): ")

if answer != "Y" and answer != "y":
    print("Recieved negative answer.")
    print("Please update file robot.json to reflect current state, or change state of the robot.")
    print("Exiting.")
    exit()
else:
    print("Recieved positive answer, continuing.")


# ==================================================
# SECTION: Parameter Helper Functions
# ==================================================

# helper function to save the current state of the machine into the file, as we will save many times during the protocol incase the protocol is interrupted
def save_parameters():
    parametersLock.acquire()
    # serialize robot parameters back into .json
    robot["coupons"] = xArm.coupons
    robot["rings"] = xArm.rings
    robot["discard"] = xArm.discards
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
    
    xArm.coupons = robot["coupons"]
    xArm.rings = robot["rings"]
    xArm.discards = robot["discard"]

    globals()["opentrons_stand_status"] = robot["opentrons_stand_status"]
    xArm.camera_box_open = robot["camera_box_open"]

    parametersLock.release()

# ==================================================
# SECTION: Compression Tester Helper Functions
# ==================================================

# simulation zero tests if compression tester is not working
def simulate_zero_and_place_coupon():
    # acquire locks
    armLock.acquire()
    compressionTesterLock.acquire()
    
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
    
    # release locks
    compressionTesterLock.release()
    armLock.release()


# ==============================================================================================================================
# SECTION: Main Function
# ==============================================================================================================================

def run_test(param = None):
    
    # ====================================================================================================
    # SECTION: Load Variables
    # ====================================================================================================

    load_parameters()
    
    # check for errors
    error_check()

    # variable declaration
    pullcast_speed = 10
    nitrogen = False
    coupon_to_bath_wait_time = 5
    nips_bath_time = 5
    second_bath_time = 5

    simulate_zero_and_place_coupon()
    print("Beginning zero tests on coupons.")
    
    # ====================================================================================================
    # SECTION: Dispense and Pullcast
    # ====================================================================================================

    # pullcast membrane
    armLock.acquire()
    xArm.pullcast(speed = pullcast_speed)
    print("Pullcast complete.")

    # ====================================================================================================
    # SECTION: Membrane formation
    # ====================================================================================================

    # foreground task: do NIPS stuff, coupon will sit on opentrons stand
    if nitrogen:
        xArm.put_cap(hover_time = coupon_to_bath_wait_time)
        print("Nitrogen off.")
    else:
        time.sleep(coupon_to_bath_wait_time)

    # place coupon in water bath
    xArm.put_coupon_bath()
    globals()["opentrons_stand_status"] = "empty"
    save_parameters()

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

    # ====================================================================================================
    # SECTION: Iniatial Picture
    # ====================================================================================================

    # acquire thread locks
    armLock.acquire()

    # move coupon to the camera 2nd bath
    xArm.pick_up("coupon bath", pitch = False)
    xArm.put_down("2nd bath", pitch = False)

    armLock.release()

    # take pre-test picture of membrane
    armLock.acquire()
    xArm.pick_up("2nd bath")
    xArm.put_down("coupon camera tester", pitch = False)
    xArm.currentZone = "middle" # speed up process
    xArm.close_camera_box()

    # ====================================================================================================
    # SECTION: Compression tests
    # ====================================================================================================

    # move coupon to compression tester
    xArm.open_camera_box()
    xArm.currentZone = "tester" # speeds up process
    xArm.pick_up("coupon camera tester", pitch = False)
    xArm.put_down("coupon angled tester", pitch = False)
          
    # take coupon to compression tester
    compressionTesterLock.acquire()
    xArm.prep_coupon_test()
            
    print("Simulating compression tests.")
    for test in tests:
        xArm.put_down(test)
        xArm.pick_up(test)

    # put coupon back on intermediate platform
    xArm.unprep_coupon_test()
            
    # ====================================================================================================
    # SECTION: Final Picture
    # ====================================================================================================

    xArm.open_camera_box()
    xArm.pick_up("coupon angled tester", pitch = False)
                
    # go put the coupon in the box for the post-test picture
    xArm.put_down("coupon camera tester", pitch = False)
    xArm.currentZone = "middle"
    xArm.close_camera_box()

    # ====================================================================================================
    # SECTION: Clean up
    # ====================================================================================================

    # put coupon in discard pile
    xArm.open_camera_box()
    xArm.currentZone = "tester" # speeds up process
    xArm.pick_up("coupon camera tester", pitch = False)
    xArm.discard(pitch = False)
    save_parameters() 

    # ensure knife is clean
    armLock.release()              
    xArm.clean_knife(brush_cycles = 5, dry_cycles = 15)
    armLock.acquire()               

    # dry compression tester
    xArm.dry_tester()  

    # always end in middle, as next run will assume we're in the middle
    xArm.immigrate("middle")
    armLock.release()
    
    # finish
    print("Done")
    