# import libraries
import json
import time
import sys
sys.path.append("/var/lib/jupyter/notebooks/2025-07-02/lib/")
from arm import Arm
from arduino import Uno
import url

# load robot parameters from .json
with open('robot.json') as robot_file:
    robot = json.load(robot_file)

coupons = robot["coupons"]
rings = robot["rings"]
discard = robot["discard"]

# initialize Arm, Arduino (CompressionTester & NitrogenBlower), Chiller, & Opentrons
arduino = Uno() # compression tester should not be connected to arduino while initializing, may accidentally start test
xArm = Arm(coupons = coupons, rings = rings, discards = discard)
xArm.open_gripper()

# helper function to save the current state of the machine into the file, as we will save many times during the protocol incase the protocol is interrupted
def save_parameters():
    # serialize robot parameters back into .json
    robot["coupons"] = xArm.coupons
    robot["rings"] = xArm.rings
    robot["discard"] = xArm.discards

    with open('robot.json', "w") as robot_file:
        json.dump(robot, robot_file)

# load parameters from .json file
with open('parameters.json') as file:
    parameters = json.load(file)

# take coupon to compression tester
xArm.prep_coupon_test()

# move coupon to the test points, and then run the tests (zero test + 3 membrane tests)
tests = ["coupon test 0", "coupon test 1", "coupon test 2", "coupon test 3"]

safe = True
recent = True
while True:
    for test in tests:
        if safe and recent:
            xArm.put_down(test)
            safe = not arduino.run_test()
        if safe:
            time.sleep(5) # make sure newton software has finished processing the test into a .csv file
            # use the data from the laptop to make sure the test finished correctly
            data = url.get()
            safe = data["safe"]
            recent = (time.time() - data["time"]) < 30
            print("Safe: " + str(safe))
            print("Recent: " + str(recent))
            print("Time: " + str(time.time()))
            print("mTime: " + str(data["time"]))
        if safe and recent:
            xArm.pick_up(test)

        if not safe:
            print("Compression tester is unsafe! exiting...")
            xArm.immigrate("middle")
            sys.exit()
        elif not recent:
            print("Compression test is out of date, tester could still be running. Unsure. exiting...")
            xArm.immigrate("middle")
            sys.exit()

# put coupon back on intermediate platform
xArm.unprep_coupon_test()

# put coupon in discard pile
xArm.pick_up("coupon angled tester")
xArm.discard()
save_parameters() # number of assemblies in discard pile has changed, update file

# always end in middle, as next run will assume we're in the middle
xArm.immigrate("middle")