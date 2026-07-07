# import libraries
import json
import time
import sys
sys.path.append("/var/lib/jupyter/notebooks/2025-07-02/lib/")
from arm import Arm
from ot2 import OT2
from chiller import BathChiller
from arduino import Uno
import url

# load robot parameters from .json
with open('robot.json') as robot_file:
    robot = json.load(robot_file)

coupons = robot["coupons"]
rings = robot["rings"]
discard = robot["discard"]
tip_index = robot["tip_index"]
heater_well_index = robot["heater_well_index"]

# make sure we have at least 1 ring and 1 coupon
errors = ""
if coupons <= 0:
    errors += "There must be at least 1 coupon in the pile. \n"
if rings <= 0:
    errors += "There must be at least 1 ring on the stand. \n"
if errors != "":
    print(errors)
    print("Please add rings or coupons, and update robot.json accordingly. Exiting.")
    exit()

# initialize Arm, Arduino (CompressionTester & NitrogenBlower), Chiller, & Opentrons
chiller = BathChiller()
arduino = Uno() # compression tester should not be connected to arduino while initializing, may accidentally start test
xArm = Arm(coupons = coupons, rings = rings, discards = discard)
opentrons = OT2(tip_index = tip_index, heater = True, heater_well_index = heater_well_index)

opentrons._drop() # drop tip if we have one
xArm.open_gripper()

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

# helper function to save the current state of the machine into the file, as we will save many times during the protocol incase the protocol is interrupted
def save_parameters():
    # serialize robot parameters back into .json
    robot["coupons"] = xArm.coupons
    robot["rings"] = xArm.rings
    robot["discard"] = xArm.discards
    robot["tip_index"] = opentrons.tip_index
    robot["heater_well_index"] = opentrons.heater_well_index

    with open('robot.json', "w") as robot_file:
        json.dump(robot, robot_file)

# load parameters from .json file
with open('parameters.json') as file:
    parameters = json.load(file)

# place new coupon
xArm.pick_up_coupon()
save_parameters() # number of coupons has changed, update file
xArm.put_down("coupon angled opentrons")

# move arm out of the way
xArm.immigrate("middle")
      
# set temperatures of different things
mixing_temp = parameters["mixing_temp"]
bath_temp = parameters["bath_temp"]

opentrons._set_temp(mixing_temp) # does not seem to be a convenient way to make sure we have hit the desired temp, but setting this before waiting for the chiller (which will take a while) makes it reasonably likely that we will hit the correct temp
chiller.go_to_temperature(bath_temp)


# mix solution
desired_weight_percent = parameters["weight_percent"]
total_vol = parameters["volume"]

if desired_weight_percent == opentrons.get_stock_weight_percent(): # pull directly from media bottle
    opentrons.attach_next_tip()
    save_parameters() # tip index has changed
    opentrons.prep_pullcast(9, 0, total_vol) # directly from stock bottle
else:
    opentrons._prepare_solution(desired_weight_percent, total_vol)
    save_parameters() # tip index & heater well index should have changed, update file incase we end the protocol early
    # opentrons prep for cast from mixing
    opentrons.prep_pullcast_from_mix(total_vol, True)
opentrons._drop()


xArm.pullcast(speed = parameters["pullcast_speed"])
# leaves knife in bath while we do nips


# cap and bath stuff (nips)
nitrogen = parameters["nitrogen"]
coupon_to_bath_wait_time = parameters["coupon_to_bath_wait_time"]

if nitrogen:
	arduino.start_blow()
	xArm.put_cap(hover_time = coupon_to_bath_wait_time)
	arduino.stop_blow()
else:
	time.sleep(coupon_to_bath_wait_time)

xArm.put_coupon_bath()

if nitrogen:
	xArm.pick_up("cap bath")
	xArm.put_down("cap stand")

# rings stuff
xArm.pick_up_ring()
save_parameters() # number of rings has changed, update file
xArm.put_down("ring bath")

# go clean the knife
xArm.pick_up("knife bath")
xArm.brush_knife(cycles=5)
xArm.dry_knife(cycles=15)
xArm.put_down("knife stand")


# nips takes like 30 minutes or something so this step takes a while, in the future try to use threads to do other things during this time
nips_bath_time = parameters["nips_bath_time"]

time.sleep(nips_bath_time)


# move coupon to intermediate tester platform
xArm.pick_up("coupon bath", pitch = False)
xArm.put_down("coupon angled tester", pitch = False)

# take coupon to compression tester
xArm.prep_coupon_test()

# move coupon to the test points, and then run the tests (zero test + 3 membrane tests)
tests = ["coupon test 0", "coupon test 1", "coupon test 2", "coupon test 3"]

safe = True
recent = True
for test in tests:
    if safe and recent:
        xArm.put_down(test)
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