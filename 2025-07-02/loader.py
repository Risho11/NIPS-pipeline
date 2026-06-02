# import libraries
import json
import sys
sys.path.append("/var/lib/jupyter/notebooks/2025-07-02/lib/")
from arm import Arm

# load robot parameters from .json
with open('robot.json') as robot_file:
    robot = json.load(robot_file)

coupons = robot["coupons"]
rings = robot["rings"]
discard = robot["discard"]
tip_index = robot["tip_index"]
heater_well_index = robot["heater_well_index"]

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
answer = input("is this correct? (Y/N)")

if answer != "Y" and answer != "y":
    print("Recieved negative answer.")
    print("Please update file robot.json to reflect current state, or change state of the robot.")
    print("Exiting.")
    exit()
else:
    print("Recieved positive answer, continuing.")


# initialize Arm
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

# place new coupon
for i in range(5):
    xArm.pick_up("coupon angled opentrons")
    xArm.put_down_coupon()
    save_parameters() # number of coupons has changed, update file

# always end in middle, as next run will assume we're in the middle
xArm.immigrate("middle")