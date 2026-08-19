# for arm code, present only very simple interface for performing different actions
import time
import sys
sys.path.append("/var/lib/jupyter/notebooks/xArm-Python-SDK-master1")
from xarm.wrapper import XArmAPI

ip_address = "192.168.1.198"

default_speed = 250 # mm/s
waypoint_speed = 250 # mm/s
pullcast_speed = 50 # mm/s
grab_speed = 100 # mm/s

coupon_spacing = 20 # mm
ring_spacing = 15 # mm
final_thickness = 8 # mm, thickness of the final assembly we put in the discard stack

coupon_offset = [coupon_spacing, 0.3, 0, 0, 0, 0]
ring_offset = [-ring_spacing, 0, 0, 0, 0, 0]
discard_offset = [0, 0, final_thickness, 0, 0, 0]

# coordinates are in the form [x, y, z, roll, pitch, yaw]
# waypoints are absolute
waypoints = {
    "opentrons": [190, -390, 300, 180, 0, -90],
    "middle": [350, 0, 240, 180, 0, 0],
    "tester": [175, 240, 320, 180, 0, 90]
}

# objects/positions that can be picked up and put down to/from
items = {
    "knife stand": {
        "home zone": "opentrons",
        "home position": "knife stand"
    },
    "knife bath": {
        "home zone": "opentrons",
        "home position": "knife bath"
    },
    "coupon angled opentrons": {
        "home zone": "opentrons",
        "home position": "coupon angled"
    },
    "coupon bath": {
        "home zone": "middle",
        "home position": "coupon bath"
    },
    "coupon angled tester": {
        "home zone": "tester",
        "home position": "coupon angled"
    },
    "coupon test 1": {
        "home zone": "tester",
        "home position": "coupon test 1"
    },
    "coupon test 2": {
        "home zone": "tester",
        "home position": "coupon test 2"
    },
    "coupon test 3": {
        "home zone": "tester",
        "home position": "coupon test 3"
    },
    "coupon test 4": {
        "home zone": "tester",
        "home position": "coupon test 4"
    },
    "cap stand": {
        "home zone": "opentrons",
        "home position": "cap stand"
    },
    "cap opentrons": {
        "home zone": "opentrons",
        "home position": "cap"
    },
    "cap bath": {
        "home zone": "opentrons",
        "home position": "cap bath"
    },
    "ring stand": {
        "home zone": "middle",
        "home position": "ring stand"
    },
    "ring bath": {
        "home zone": "middle",
        "home position": "ring bath"
    },
    "coupon camera middle": {
        "home zone": "middle",
        "home position": "coupon camera"
    },
    "coupon camera tester": {
        "home zone": "tester",
        "home position": "coupon camera"
    },
    "squeegee": {
        "home zone": "tester",
        "home position": "squeegee stand"
    },
    "2nd bath": {
        "home zone": "tester",
        "home position": "2nd bath"
    }
}
        

# use "$NAME waypoint" to specify a specific position to take just before or after going to the position of $NAME
positions = {
    "opentrons": {
        "knife stand waypoint": [32, -365, 240, 180, 20, -90],
        "knife stand": [32, -365, 220, 180, 20, -90],
        
        "knife bath waypoint": [32, -430, 240, 180, 0, -90],
        "knife bath": [32, -460, 218, 180, 20, -90],
        "knife brush waypoint": [32, -420, 240, 180, 0, -90],
        "knife brush": [32, -438, 227, 180, 20, -90],
        "knife dry waypoint": [34, -380, 240, 180, 0, -90],
        "knife dry": [34, -395, 223, 180, 20, -90],

        "pullcast start waypoint": [215, -540+2, 240, 180, 20, 0],
        "pullcast start": [215, -540+2, 224, 180, 20, 0],
        "pullcast start pulldown": [215, -540+2, 223.9, 180, 20, 0],
        "pullcast end pulldown": [110, -540+2, 223.9, 180, 20, 0],
        "pullcast end waypoint": [110, -540+2, 240, 180, 20, 0],
        
        "coupon angled waypoint": [300, -469, 300, 180, 45, -91.5],
        "coupon angled": [300, -469, 248, 180, 45, -91.5],
        
        "cap waypoint": [300, -394, 240, 180, 0, -90],
        "cap hover": [300, -449, 248+2, 180, 30, -90],
        "cap": [300, -489-3, 261, 180, 45, -90],
        "coupon bath cap": [265, -230, 119, 180, 45, -90],
        
        "coupon bath waypoint": [262, -228, 240, 180, 45, -91.5],
        "coupon bath": [262, -228-1, 113, 180, 45, -91.5], # slight offset to correct positioning issue
        
        "cap stand waypoint": [70, -304, 300, 180, 65, 0],
        "cap stand": [0, -304, 200, 180, 45, 0],
        "cap bath waypoint": [260, -230, 240, 180, 45, -90],
        "cap bath": [260, -242, 135, 180, 40, -90]
    },
    "middle": {
        "coupon bath waypoint": [262, -228, 240, 180, 45, -91.5],
        #"coupon bath cap": [270, -230, 119, 180, 45, -90],
        "coupon bath": [262, -228, 115, 180, 45, -91.5],
        
        #"cap stand waypoint": [70, -308, 300, 180, 65, 0],
        #"cap stand": [0, -308, 200, 180, 45, 0],
        #"cap bath waypoint": [265, -230, 240, 180, 45, -90],
        #"cap bath": [265, -240, 135, 180, 40, -90],
        
        "ring rack waypoint": [370, 0, 240, 180, 30, 0],
        "ring rack": [370, 0, 170, 180, 30, 0],
        "ring bath waypoint": [262, -353, 240, 180, 90, -90],
        "ring bath": [262, -353, 138, 180, 90, -90],
        #"coupon rack waypoint": [222, -3, 230, 180, 45, 0],
        #"coupon rack": [222, -3, 137, 180, 45, 0],
        "coupon rack waypoint": [222, -2, 230, 180, 45, 0],
        "coupon rack": [182, -2, 175, 180, 90, 0],
        "coupon rack back": [182 - 30, -3, 175 + 30, 180, 90, 0],
        
        "camera open waypoint": [393, 70, 250, 180, 45, 90],
        "camera open": [393, 70, 147, 180, 45, 90],
        "camera closed": [395 - 178, 70, 147, 180, 45, 90],
        "camera closed waypoint": [395 - 178, 70, 180, 180, 45, 90],
        
        "coupon camera": [400 - 142, 88, 147, 180, 45, 88],
        "coupon camera waypoint": [400 - 142, 88, 150 + 150, 180, 45, 88]
    },
    "tester": {
        "coupon camera": [400 - 142, 88, 147, 180, 45, 88],
        "coupon camera waypoint": [400 - 142, 88, 150 + 150, 180, 45, 88],
        
        "coupon angled waypoint": [380, 330, 350, 180, 45, 90],
        "coupon angled": [380, 330, 314, 182, 45, 90],
        "coupon flat waypoint": [380, 260, 270, 180, 0, 90],
        "coupon flat": [380, 260, 224, 180, 0, 90],

        # coupon tests positions
        "coupon test 1 waypoint": [175, 260, 224, 180, 0, 90],
        "coupon test 2 waypoint": [175, 260, 224, 180, 0, 90],
        "coupon test 3 waypoint": [175, 260, 224, 180, 0, 90], # all tests use the same waypoint
        "coupon test 4 waypoint": [175, 260, 224, 180, 0, 90],
        #"coupon test 1": [160, 360, 223.5, 180, 1, 90],
        #"coupon test 2": [170, 360, 223.5, 180, 1, 90],
        #"coupon test 3": [180, 360, 223.5, 180, 1, 90],
        #"coupon test 4": [150, 360, 223.5, 180, 1, 90], # only used for testing the flatness of the coupon, membrane tests only use 3 points
        "coupon test 1": [160, 355, 223.5, 180, 1, 90],
        "coupon test 2": [170, 355, 223.5, 180, 1, 90],
        "coupon test 3": [160, 365, 223.5, 180, 1, 90],
        "coupon test 4": [170, 365, 223.5, 180, 1, 90],
        
        #"discard waypoint": [40, 250, 350, 180, 45, 90],
        #"discard": [40, 250, 136, 180, 45, 90],
        "discard waypoint": [0, 240, 350, 180, 45, 90], # new discard bath location
        "discard": [-2, 280, 117, 180, 45, 90],
        
        "2nd bath waypoint": [280, 240, 300, 180, 45, 89], # leave in bath
        "2nd bath": [286, 250, 113, 180, 45, 89],
        "hover bath waypoint": [270, 225, 310, 180, 45, 90], # arm holds coupon in bath
        "hover bath": [270, 225, 170, 180, 45, 90],
        
        "squeegee stand waypoint 1": [100, 165, 250, 180, 0, 90],
        "squeegee stand waypoint 2": [100, 165, 185, 180, 0, 90],
        "squeegee stand waypoint": [94, 288, 185, 180, 0, 90],
        "squeegee stand": [94, 288, 163, 180, 0, 90],
        
        "squeegee 1 waypoint 1": [270, 200, 254, 180, 0, 90],
        "squeegee 1 waypoint 2": [270, 400, 254, 180, 0, 90],
        "squeegee 1 waypoint 3": [242, 420, 261, 180, 0, 90],
        "squeegee 1 start": [242, 420, 259, 180, 10, 90],
        "squeegee 1 end": [242, 180, 251, 180, 10, 90],
        
        "squeegee 2 waypoint 1": [60, 200, 245, 180, 0, 90],
        "squeegee 2 waypoint 2": [60, 400, 245, 180, 0, 90],
        "squeegee 2 waypoint 3": [100, 420, 261, 180, 0, 90],
        "squeegee 2 start": [95, 420, 257, 180, 10, 90],
        "squeegee 2 end": [95, 180, 249, 180, 10, 90],
        
        "squeegee middle waypoint 1": [160, 180, 254, 180, 0, 90],
        "squeegee middle waypoint 2": [160, 280, 254, 180, 0, 90],
        "squeegee middle start": [160, 310, 254, 180, 10, 90],
        "squeegee middle end": [160, 180, 249, 180, 10, 90],
        
        #"squeegee pin waypoint": [60, 195, 230, 180, 0, 90],
        #"squeegee pin": [60, 330, 230, 180, 0, 90],
        "squeegee pin waypoint": [60, 328, 227, 180, 0, 90],
        "squeegee pin": [130, 328, 227, 180, 0, 90],
    }
}

# actual arm class, the whole point of this file
class Arm():
    xArm = None
    currentZone = None
    rings = 0
    coupons = 0
    discards = 0
    camera_box_open = None

    # ==================================================
    # SECTION: Tier 1 Functions
    # ==================================================
    
    def clean(self):
        self.xArm.clean_error()
        self.xArm.clean_bio_gripper_error()
        self.xArm.motion_enable()
        self.xArm.set_bio_gripper_enable()
    
    # put the arm into teaching mode, mostly useful for moving the arm by hand after it crashes when testing
    def teach(self):
        self.xArm.set_mode(2) # teaching mode
        self.xArm.set_state(0)
    
    # likely will be made internal later, but currently exposed for testing, should not be called in protocol script
    def go_to(self, coordinates, speed = default_speed, pitch = True):
        if pitch:
            self.xArm.set_position(x=coordinates[0], y=coordinates[1], z=coordinates[2], roll=coordinates[3], pitch=coordinates[4], yaw=coordinates[5], speed=speed, wait = True)
        else:
            self.xArm.set_position(x=coordinates[0], y=coordinates[1], z=coordinates[2], roll=coordinates[3], yaw=coordinates[5], speed=speed, wait = True)

    def go_to_offset(self, coordinates, offset, speed = default_speed, pitch = True):
        if pitch:
            self.xArm.set_position(x=coordinates[0]+offset[0], y=coordinates[1]+offset[1], z=coordinates[2]+offset[2], roll=coordinates[3]+offset[3], pitch=coordinates[4]+offset[4], yaw=coordinates[5]+offset[5], speed=speed, wait = True)
        else:
            self.xArm.set_position(x=coordinates[0]+offset[0], y=coordinates[1]+offset[1], z=coordinates[2]+offset[2], roll=coordinates[3]+offset[3], yaw=coordinates[5]+offset[5], speed=speed, wait = True)

    # inialization of arm
    def __init__(self, coupons=1, rings=1, discards = 0, home=True, camera_box_open = True):
        self.xArm = XArmAPI(ip_address)
        self.clean()
        self.xArm.motion_enable()
        self.xArm.set_mode(0) # position control mode
        
        if home:
            self.xArm.reset()
        
            # start at middle waypoint
            self.currentZone = "middle"
            self.go_to(waypoints["middle"])
        
        # for keeping track of next coupon and next ring
        self.coupons = coupons
        self.rings = rings
        self.discards = discards
        
        self.camera_box_open = camera_box_open
        
        # gripper stuff
        self.xArm.open_bio_gripper()
        self.xArm.set_bio_gripper_force(100)

    # simple gripper functions
    def close_gripper(self):
        self.xArm.close_bio_gripper()
            
    def open_gripper(self):
        self.xArm.open_bio_gripper()

    # ==================================================
    # SECTION: Tier 2 Functions
    # ==================================================

    # go from current zone to destination zone, using waypoints
    def immigrate(self, destination, pitch = True):
        self.go_to(waypoints[self.currentZone], pitch=pitch)
        
        if (destination == "tester" or destination == "opentrons") and self.currentZone != "middle" and self.currentZone != destination:
            self.go_to(waypoints["middle"], speed=waypoint_speed, pitch=pitch)
        
        self.go_to(waypoints[destination], speed=waypoint_speed, pitch=pitch)
        self.currentZone = destination
    
    # go to named position, automatically immigrate to new zone if required
    def go_to_position(self, zone, position, speed = default_speed, pitch = True):
        if zone != self.currentZone:
            self.immigrate(zone, pitch = pitch)
        self.go_to(positions[zone][position], speed = speed)

    def go_to_position_offset(self, zone, position, offset, speed = default_speed, pitch = True):
        if zone != self.currentZone:
            self.immigrate(zone, pitch = pitch)
        self.go_to_offset(positions[zone][position], offset, speed = speed)
    
    def pick_up(self, item, pitch = True, speed = default_speed):
        item = items[item]
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
        self.go_to_position(item["home zone"], item["home position"], speed = default_speed)
        self.close_gripper()
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch, speed = speed)
    
    def put_down(self, item, pitch = True, speed  = default_speed, offset = [0,0,0,0,0,0]):
        item = items[item]
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
        self.go_to_position_offset(item["home zone"], item["home position"], speed = speed, offset = offset)
        self.open_gripper()
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
        
    # ==================================================
    # SECTION: Tier 3 Functions
    # ==================================================
    
    # from stand, perform pullcast on coupon, return knife to stand
    def pullcast(self, speed = pullcast_speed, force = 10):
        self.xArm.set_bio_gripper_force(force)
        self.pick_up("knife stand")
        
        # put knife on coupon (on stand)
        self.go_to_position("opentrons", "pullcast start waypoint")
        self.go_to_position("opentrons", "pullcast start")

        # reset gripper, then pull back while applying pulldown
        self.open_gripper()
        self.close_gripper()
        self.go_to_position("opentrons", "pullcast start pulldown")
        self.go_to_position("opentrons", "pullcast end pulldown", speed = speed)# actual pull
        self.go_to_position("opentrons", "pullcast end waypoint")
        # move so arm doesn't hit solution bottle
        #self.go_to_position_offset("opentrons", "pullcast end waypoint", [0,80,0,0,0,-45])
        self.immigrate("opentrons")
        
        self.put_down("knife bath")
        self.xArm.set_bio_gripper_force(100)


    # placing cap requires a special method as we need to hover the cap for some time before placing
    # but can be removed with the normal pick_up() method
    def put_cap(self, hover_time):
        self.pick_up("cap stand")
        
        self.go_to_position("opentrons", "cap waypoint")
        self.go_to_position("opentrons", "cap hover")
        
        time.sleep(hover_time)
        
        self.go_to_position("opentrons", "cap")
        self.open_gripper()
        self.go_to_position("opentrons", "cap waypoint")
    
    # putting the coupon into the bath also requires a special method, due to the magnets used to remove the cap
    def put_coupon_bath(self):
        self.pick_up("coupon angled opentrons", pitch = False)
        
        self.go_to_position("opentrons", "coupon bath waypoint", pitch = False)
        #self.go_to_position("opentrons", "coupon bath cap")
        self.go_to_position("opentrons", "coupon bath", speed = 50)
        
        self.open_gripper()
        self.go_to_position("opentrons", "coupon bath waypoint")

    # from coupon on intermediate tester stand, move to coupon test waypoint
    # used to help make protocol easier to read when doing compression tests
    def prep_coupon_test(self):
        self.go_to_position("tester", "coupon flat waypoint")
        self.go_to_position("tester", "coupon flat")
        self.close_gripper()
        self.go_to_position("tester", "coupon test 1 waypoint")
        
    def unprep_coupon_test(self):
        self.go_to_position("tester", "coupon test 1 waypoint")
        self.go_to_position_offset("tester", "coupon flat", [0, 6, 0, 0, 0, 0])
        self.open_gripper()
        self.go_to_position("tester", "coupon flat waypoint")
        
    # picking up and putting down coupons requires a special method because of the variable offset
    def pick_up_coupon(self):                                                                                  
        if self.coupons < 0:
            return
        self.coupons -= 1
        offset = [coordinate * self.coupons for coordinate in coupon_offset]
        self.go_to_position("middle", "coupon rack waypoint")
        self.go_to_position_offset("middle", "coupon rack", offset)
        self.close_gripper()
        self.go_to_position_offset("middle", "coupon rack back", offset)
        self.go_to_position("middle", "coupon rack waypoint")
                                                                                                             
    def put_down_coupon(self):
        offset = [coordinate * self.coupons for coordinate in coupon_offset]
        self.go_to_position("middle", "coupon rack waypoint")
        self.go_to_position_offset("middle", "coupon rack back", offset)
        self.go_to_position_offset("middle", "coupon rack", offset)
        self.open_gripper()
        self.go_to_position("middle", "coupon rack waypoint")
        self.coupons += 1
    
    # same idea but only for putting down, don't need to pick up from the discard pile
    def discard(self, pitch = False):
        offset = [coordinate * self.discards for coordinate in discard_offset]
        self.go_to_position("tester", "discard waypoint", pitch = pitch)
        self.go_to_position_offset("tester", "discard", offset, pitch = pitch)
        self.open_gripper()
        self.go_to_position("tester", "discard waypoint", pitch = pitch)
        self.discards += 1
        
    # similar idea for the rings, but also  offset the waypoints
    def pick_up_ring(self):                                                                                  
        if self.rings < 0:
            return
        self.rings -= 1
        offset = [coordinate * self.rings for coordinate in ring_offset]
        self.go_to_position_offset("middle", "ring rack waypoint", offset)
        self.go_to_position_offset("middle", "ring rack", offset)
        self.close_gripper()
        self.go_to_position_offset("middle", "ring rack waypoint", offset)

    def put_down_ring(self):              
        offset = [coordinate * self.rings for coordinate in ring_offset]
        self.go_to_position_offset("middle", "ring rack waypoint", offset)
        self.go_to_position_offset("middle", "ring rack", offset)
        self.open_gripper()
        self.go_to_position_offset("middle", "ring rack waypoint", offset)
        self.rings += 1

    def close_camera_box(self):
        if self.camera_box_open:
            self.close_gripper()
            self.go_to_position("middle", "camera open waypoint")
            self.go_to_position("middle", "camera open")
            self.go_to_position("middle", "camera closed")
            self.go_to_position("middle", "camera closed waypoint")

            self.go_to_position_offset("middle", "camera closed waypoint", [50,0,0,0,0,0])
            self.camera_box_open = False

    def open_camera_box(self):
        if not self.camera_box_open:
            self.close_gripper()
            self.go_to_position("middle", "camera closed waypoint")
            self.go_to_position("middle", "camera closed")
            self.go_to_position_offset("middle", "camera open", [4,0,0,0,0,0]) # ensure box is fully open
            self.go_to_position_offset("middle", "camera open", [-2,0,0,0,0,0]) 
            self.go_to_position("middle", "camera open waypoint")
            self.open_gripper()
            self.camera_box_open = True

    # cleans knife        
    def clean_knife(self, brush_cycles = 5, dry_cycles = 5):
        # grab knife
        self.pick_up("knife bath")
        
        # brush knife
        self.go_to_position("opentrons", "knife brush waypoint")
        self.go_to_position("opentrons", "knife brush")
        for i in range(brush_cycles): # brush front to back
            self.go_to_position_offset("opentrons", "knife brush", [0,20,0,0,0,0])
            self.go_to_position_offset("opentrons", "knife brush", [0,-30,0,0,0,0])
        for i in range(brush_cycles): # brush horizontally
            self.go_to_position_offset("opentrons", "knife brush", [18,0,0,0,0,0])
            self.go_to_position_offset("opentrons", "knife brush", [-18,0,0,0,0,0])
        self.go_to_position("opentrons", "knife brush")
        self.go_to_position("opentrons", "knife brush waypoint")
        
        # dry knife
        self.go_to_position("opentrons", "knife dry waypoint")
        self.go_to_position("opentrons", "knife dry")
        for i in range(dry_cycles):
            self.go_to_position_offset("opentrons", "knife dry", [18,0,0,0,0,0])
            self.go_to_position_offset("opentrons", "knife dry", [-18,0,0,0,0,0])
        self.go_to_position("opentrons", "knife dry")
        self.go_to_position("opentrons", "knife dry waypoint")
        
        # put knife back on stand
        self.put_down("knife stand")

    # helper function for dry_tester()
    def squeegee(self, position, speed):
        self.go_to_position("tester", "squeegee " + position + " waypoint 1")
        self.go_to_position("tester", "squeegee " + position + " waypoint 2")
        self.go_to_position("tester", "squeegee " + position + " start")
        self.go_to_position("tester", "squeegee " + position + " end", speed = speed)

    # dries the compression tester    
    def dry_tester(self, squeegee_cycles = 1, pin_cycles = 2, speed = 250, middle = True):
        # pickup squeegee
        self.go_to_position("tester", "squeegee stand waypoint 1")
        self.go_to_position("tester", "squeegee stand waypoint 2")
        self.pick_up("squeegee")
        self.go_to_position("tester", "squeegee stand waypoint 2")
        self.go_to_position("tester", "squeegee stand waypoint 1")
        
        # squeegee testing platform
        for i in range(squeegee_cycles):
            self.squeegee(position = "1", speed = speed)
            self.squeegee(position = "2", speed = speed)
        
        # dry compression pin
        if pin_cycles > 0:
            self.go_to_position("tester", "squeegee 2 waypoint 1")
            self.go_to_position("tester", "squeegee pin waypoint")
            for i in range(pin_cycles):
                self.go_to_position("tester", "squeegee pin", speed = 50)
                self.go_to_position_offset("tester", "squeegee pin", [20,0,0,0,0,0], speed = 50)
            self.go_to_position("tester", "squeegee pin waypoint", speed = 50)
            
            # remove water on left side again
            self.squeegee(position = "2", speed = speed)
        
        # squeegee middle
        if middle:
            self.squeegee(position = "middle", speed = speed)
        
        # put away squeegee
        self.go_to_position("tester", "squeegee stand waypoint 1")
        self.go_to_position("tester", "squeegee stand waypoint 2")
        self.put_down("squeegee")
        self.go_to_position("tester", "squeegee stand waypoint 2")
        self.go_to_position("tester", "squeegee stand waypoint 1")

        
       