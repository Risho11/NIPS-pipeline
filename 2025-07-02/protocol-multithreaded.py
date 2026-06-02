# import libraries
import json
import time
import sys
sys.path.append("/var/lib/jupyter/notebooks/2025-07-02/lib/")
from arm import Arm
from ot2 import OT2
from chiller import BathChiller
from arduino import Uno
import url as url

import threading

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
xArm = Arm(coupons = coupons, rings = rings, discards = discard, camera_box_open = camera_box_open)
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

                    # move coupon to the test points, and then run the zero tests (3 tests where the membrane will be)
                    tests = ["coupon test 1", "coupon test 2", "coupon test 3"]

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

def delayed_knife_cleaning(delay = 0):
    time.sleep(delay)
    
    armLock.acquire()
    # go clean the knife
    xArm.pick_up("knife bath")
    xArm.brush_knife(cycles=5)
    xArm.dry_knife(cycles=15)
    xArm.put_down("knife stand")
    armLock.release()

def run_test(param = None):
    if param == None:
        # load parameters from .json file
        with open('parameters.json') as file:
            parameters = json.load(file)
    else:
        parameters = param
    
    load_parameters()

    # Background task 1: start chilling the chiller
    bath_temp = parameters["bath_temp"]
    chiller_process = threading.Thread(target=chiller.go_to_temperature, args=(bath_temp, ))
    chiller_process.start()
    # Background task 2: take a clean coupon, run the three zero tests on it, then place it into the opentrons
    place_coupon_process = threading.Thread(target = zero_and_place_coupon)
    place_coupon_process.start()
    
    # Foreground task: mix/asperate the correct concentration of solution
    opentronsLock.acquire()
    
    # mix solution
    desired_weight_percent = parameters["weight_percent"]
    total_vol = parameters["volume"]

    if desired_weight_percent == opentrons.get_stock_weight_percent(): # pull directly from media bottle
        opentrons.attach_next_tip()
        save_parameters() # tip index has changed
        opentrons.prep_pullcast_asperate(9, 0, total_vol) # directly from stock bottle
    else:
        mixing_temp = parameters["mixing_temp"]
        if(opentrons.has_temp):
            opentrons._set_temp(mixing_temp) # does not seem to be a convenient way to make sure we have hit the desired temp, so we set it at least before we start pulling solutions from the stock bottles, which will take some time
        opentrons._prepare_solution(desired_weight_percent, total_vol)
        save_parameters() # tip index & heater well index should have changed, update file incase we end the protocol early
        # opentrons prep for cast from mixing
        opentrons.prep_pullcast_from_mix_asperate(total_vol, True)
    
    # make sure the chiller is at temp and that the clean (and zeroed) coupon has been placed before continuing
    chiller_process.join()
    place_coupon_process.join()
    # 0 background tasks now
    print("Joined both subprocesses")
    
    # from here until we put the coupon in the camera box, we technically can't release the arm or anything, since everything has a deadline
    # therefore we need to lock the camera box right now even though we won't use it for like 30 minutes or so
    # but we need to make sure that we aren't waiting for it
    done = False
    while not done:
        if armLock.acquire(False):
            print("ArmLock Acquired")
            if cameraLock.acquire(False):
                print("CameraLock Acquired")
                xArm.open_camera_box()
                done = True
                break
                
                cameraLock.release()
                print("CameraLock Released")
            armLock.release()
            print("ArmLock Released")
    
    # dispense and then pullcast
    opentronsStandLock.acquire()
    opentrons.prep_pullcast_dispense(total_vol)
    globals()["opentrons_stand_status"] = "dirty"
    save_parameters()
    dropProcess = threading.Thread(target = opentrons._drop)
    dropProcess.start()
    
    xArm.pullcast(speed = parameters["pullcast_speed"])

    # don't need the opentrons anymore, just the stand
    dropProcess.join()
    opentronsLock.release()
    
    # don't release the arm or opentrons stand, we still need them to be ours
    # I would really like a way to be able to release the arm temporarily, but currently the only way to make sure we will have the arm in time to meet the coupon_to_bath_wait_time deadline is to hold the arm for now
    # perhaps we figure out how long each background task will take and only release it if the combined time of all background tasks is shorter than the time we have to wait for? kind of like preemptive multitasking
    # or maybe add a way to forcefully pause the background tasks and take the arm from them if we need it here?
    
    # new background task 1: clean the knife
    # wait at least 5 minutes before trying to clean the knife (currently we won't release the arm until after we place the rings but hey maybe in the future we'll figure out some premption or something)
    # we will join this process at the end of the protocol most likely since we don't actually care about the knife it's very low priority as long as it's clean for the next run
    knife_cleaning_process = threading.Thread(target=delayed_knife_cleaning, args=(300, ))
    knife_cleaning_process.start()

    # foreground task: do NIPS stuff
    nitrogen = parameters["nitrogen"]
    coupon_to_bath_wait_time = parameters["coupon_to_bath_wait_time"]

    if nitrogen:
        arduino.start_blow()
        xArm.put_cap(hover_time = coupon_to_bath_wait_time)
        arduino.stop_blow()
    else:
        time.sleep(coupon_to_bath_wait_time)

    xArm.put_coupon_bath()
    globals()["opentrons_stand_status"] = "empty"
    save_parameters()
    opentronsStandLock.release() # we aren't using the opentrons stand anymore
    
    # background task 2: start a timer for nips in the background, since this timer should start as close to when the coupon is placed in the water, rather than after we put the cap away and add a ring
    nips_bath_time = parameters["nips_bath_wait_time"]
    nips_timer_process = threading.Thread(target=time.sleep, args=(nips_bath_time, ))
    nips_timer_process.start()

    if nitrogen:
        xArm.pick_up("cap bath")
        xArm.put_down("cap stand")

    # rings stuff
    xArm.pick_up_ring()
    save_parameters() # number of rings has changed, update file
    xArm.put_down("ring bath")

    # technically like I said earlier we shouldn't release the arm here, since we have no way of ensuring that we'll be able to get it back before the nips_bath_time deadline
    # really sucks but I want to make sure this program hits all the deadlines properly no matter what
    
    # wait until the nips timer is up
    nips_timer_process.join()


    # move coupon to the camera to take the pre-test picture
    xArm.pick_up("coupon bath", pitch = False)
    xArm.immigrate("middle", pitch = False) # try not to drip water on the next coupon in the stack
    xArm.put_down("coupon camera middle", pitch = False)
    
    xArm.close_camera_box()
    # we could release the arm here, since now we don't have any deadlines, but it makes more sense to hold onto the arm until we put the coupon in the compression tester
    # taking the snapshot doesn't take very long, so if another process takes the arm during that time, we'd be stuck waiting to get the arm back
    # it makes more sense to hold onto the arm until we start the compression test, because that will take a while, so we won't be wasting so much time if another process (most likely the knife cleaning process) takes the arm for a bit
    #armLock.release()
    time.sleep(5) # make sure the camera has time to adjust to the lighting and everything
    url.take_snapshot()
    
    # we need the arm back and to get the compression tester
    done = False
    while not done:
        #if armLock.acquire(False):
            if compressionTesterLock.acquire(False):
                xArm.open_camera_box()
                xArm.pick_up("coupon camera tester", pitch = False)
                cameraLock.release() # don't need the camera box right now
                xArm.put_down("coupon angled tester", pitch = False)
                # take coupon to compression tester
                xArm.prep_coupon_test()
                
                # move coupon to the test points, and then run the tests (3 membrane tests, no need for zero tests they were already done)
                tests = ["coupon test 1", "coupon test 2", "coupon test 3"]

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
                    xArm.immigrate("middle")
                    armLock.acquire()
                    sys.exit()
                    
                # put coupon back on intermediate platform
                xArm.unprep_coupon_test()
                cameraLock.acquire()
                xArm.open_camera_box()
                xArm.pick_up("coupon angled tester", pitch = False)
                # go put the coupon in the box for the post-test picture
                xArm.put_down("coupon camera tester", pitch = False)
                xArm.close_camera_box()
                
                done = True
                # don't break, we want to release the arm and compression tester
                compressionTesterLock.release()
            #armLock.release()
    
    url.take_snapshot()
    #armLock.acquire()
    xArm.open_camera_box()
    
    # put coupon in discard pile
    xArm.pick_up("coupon camera tester", pitch = False)
    cameraLock.release()
    xArm.immigrate("tester", pitch = False) # go to compression tester waypoint before discarding, otherwise back of arm will crash into fume hood
    xArm.discard(pitch = False)
    save_parameters() # number of assemblies in discard pile has changed, update file

    # always end in middle, as next run will assume we're in the middle
    xArm.immigrate("middle")
    armLock.release()
    knife_cleaning_process.join() # make sure the knife is clean before we say we're done, it would cause a problem if we tried to make another membrane and the knife is not clean yet (robot.json currently does not store the status of the knife, might want to add that)
    print("Done")
    url.start_processing(parameters) # tell the pc that the test is done so it can go process the files

runProcess = None

# http server for the laptop to request to start a new membrane synthysis
from http.server import BaseHTTPRequestHandler, HTTPServer
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
        

if __name__ == '__main__':
    server = HTTPServer(("169.254.46.48", 8000), RequestHandler)
    server.serve_forever()