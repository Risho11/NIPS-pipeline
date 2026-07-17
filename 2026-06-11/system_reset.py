import sys
sys.path.append("/var/lib/jupyter/notebooks/2026-06-11/lib/")

#from arduino import Uno
#import url as url

reset_OT2 = False

# arm reset
from arm import Arm
xArm = Arm(home=False)
xArm.clean()
xArm.teach()

# heater and opentrons reset
if reset_OT2:
    from ot2 import OT2
    opentrons = OT2(tip_index = 0, heater = True, heater_well_index = 0)
    opentrons._drop() # drop tip if we have one
    if(opentrons.has_temp()): # deactivate heater
        opentrons._deactivate_temp()

    # attach tips to reset opentrons position
    opentrons._attach(8, 95)
    opentrons._drop(8, 95)
    opentrons._drop()

# turn off chiller
from chiller import BathChiller
chiller = BathChiller()
chiller.turn_off()

# exit program
print("System is reset. Exiting program.")
sys.exit()