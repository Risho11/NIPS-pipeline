import sys
import json
sys.path.append("/var/lib/jupyter/notebooks/2026-06-11/lib/")

reset_arm = True
reset_chiller = True

# arm reset
if reset_arm:
    from arm import Arm
    xArm = Arm(home=False)
    xArm.clean()
    xArm.teach()
    print("Arm reset")

    
    
    
# turn off chiller
if reset_chiller:
    from chiller import BathChiller
    chiller = BathChiller()
    chiller.turn_off()
    print("Chiller turned off")
    

    
# reset robot.json
with open('robot.json') as robot_file:
    robot = json.load(robot_file)

# rings, coupons, discard
answer = input("Reset coupons, rings, and discard? (Y/N): ")
if answer == "Y" or answer == "y":
    robot["coupons"] = 9
    robot["rings"] = 9
    robot["discard"] = 0

# pipette tips    
answer = input("Reset pipette tips? (Y/N): ")
if answer == "Y" or answer == "y":     
    robot["tip_index"] = 0

# heater well   
answer = input("Reset heater wells? (Y/N): ")
if answer == "Y" or answer == "y":     
    robot["heater_well_index"] = 0

with open('robot.json', "w") as robot_file:
    json.dump(robot, robot_file)    
    
    
    
    
# reset opentrons
answer = input("Reset Opentrons? (Y/N): ")
if answer == "Y" or answer == "y":
    from ot2 import OT2
    opentrons = OT2(tip_index = 0, heater = True, heater_well_index = 0)
    opentrons._drop() # drop tip if we have one
    if(opentrons.has_temp()): # deactivate heater
        opentrons._deactivate_temp()    

        
        
        
# exit program
print("System is reset. Exiting program.")
sys.exit()