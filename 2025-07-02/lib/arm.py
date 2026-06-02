# for arm code, present only very simple interface for performing different actions
import time
import sys
sys.path.append("/var/lib/jupyter/notebooks/xArm-Python-SDK-master1")
from xarm.wrapper import XArmAPI

# coordinates are in the form [x, y, z, roll, pitch, yaw]
# waypoints are absolute
waypoints = {
    "opentrons": [190, -390, 300, 180, 0, -90],
    "middle": [350, 0, 240, 180, 0, 0],
    "tester": [175, 280, 350, 180, 0, 90]
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
    "coupon test 0": {
        "home zone": "tester",
        "home position": "coupon test 0"
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
    }
}
        

# use "$NAME waypoint" to specify a specific position to take just before or after going to the position of $NAME
positions = {
    "opentrons": {
        "knife stand waypoint": [37.5, -365, 240, 180, 0, -90],
        "knife stand": [37.5, -365, 220, 180, 20, -90],
        "pullcast start waypoint": [215, -540, 240, 180, 20, 0],
        "pullcast start": [215, -540, 222, 180, 20, 0],
        "pullcast start pulldown": [215, -540, 221.9, 180, 20, 0],
        "pullcast end pulldown": [110, -540, 221.9, 180, 20, 0],
        "pullcast end waypoint": [110, -540, 240, 180, 20, 0],
        "coupon angled waypoint": [301, -469, 300, 180, 45, -90],
        "coupon angled": [301, -469, 248, 180, 45, -90],
        "cap waypoint": [301, -394, 240, 180, 0, -90],
        "cap hover": [301, -449, 248, 180, 30, -90],
        "cap": [301, -489, 261, 180, 45, -90],
        "knife bath waypoint": [37.5, -430, 240, 180, 0, -90],
        "knife bath": [37.5, -460, 215, 180, 20, -90],
        "knife brush waypoint": [37.5, -420, 240, 180, 0, -90],
        "knife brush 1": [37.5 + 20, -440, 225, 180, 20, -90],
        "knife brush 2": [37.5 - 20, -440, 225, 180, 20, -90],
        "knife dry waypoint": [37.5, -380, 240, 180, 0, -90],
        "knife dry 1": [37.5 + 20, -400, 220, 180, 20, -90],
        "knife dry 2": [37.5 - 20, -400, 220, 180, 20, -90],
        "coupon bath waypoint": [265, -230, 240, 180, 45, -90],
        "coupon bath cap": [270, -230, 119, 180, 45, -90],
        "coupon bath": [265, -228, 117, 180, 45, -90],
        "cap stand waypoint": [70, -308, 300, 180, 65, 0],
        "cap stand": [0, -308, 200, 180, 45, 0],
        "cap bath waypoint": [265, -230, 240, 180, 45, -90],
        "cap bath": [265, -240, 135, 180, 40, -90]
    },
    "middle": {
        "coupon bath waypoint": [265, -226, 240, 180, 45, -90],
        "coupon bath cap": [270, -230, 119, 180, 45, -90],
        "coupon bath": [265, -226, 117, 180, 45, -90],
        "cap stand waypoint": [70, -308, 300, 180, 65, 0],
        "cap stand": [0, -308, 200, 180, 45, 0],
        "cap bath waypoint": [265, -230, 240, 180, 45, -90],
        "cap bath": [265, -240, 135, 180, 40, -90],
        "ring rack waypoint": [380, 0, 240, 180, 30, 0],
        "ring rack": [380, 0, 170, 180, 30, 0],
        "ring bath waypoint": [265, -353, 240, 180, 90, -90],
        "ring bath": [265, -353, 135, 180, 90, -90],
        "coupon rack waypoint": [222, -3, 230, 180, 45, 0],
        "coupon rack": [222, -3, 137, 180, 45, 0],
        "camera open waypoint": [395, 70, 150 + 100, 180, 45, 90],
        "camera open": [395, 70, 150, 180, 45, 90],
        "camera closed": [395 - 178, 70, 150, 180, 45, 90],
        "camera closed waypoint": [395 - 178, 70, 150 + 30, 180, 45, 90],
        "coupon camera": [400 - 140, 83, 150, 180, 45, 88],
        "coupon camera waypoint": [400 - 140, 83, 150 + 150, 180, 45, 88]
    },
    "tester": {
        "coupon camera": [400 - 140, 83, 150, 180, 45, 88],
        "coupon camera waypoint": [400 - 140, 83, 150 + 150, 180, 45, 88],
        "coupon angled waypoint": [355, 330, 350, 180, 45, 90],
        "coupon angled": [355, 330, 316, 182, 45, 90],
        "coupon flat waypoint": [350, 260, 270, 180, 0, 90],
        "coupon flat": [350, 260, 224, 180, 0, 90],
        "coupon test 0 waypoint": [175, 260, 230, 180, 0, 90],
        "coupon test 1 waypoint": [175, 260, 230, 180, 0, 90],
        "coupon test 2 waypoint": [175, 260, 230, 180, 0, 90],
        "coupon test 3 waypoint": [175, 260, 230, 180, 0, 90], # all tests use the same waypoint
        "coupon test 4 waypoint": [175, 260, 230, 180, 0, 90],
        "coupon test 0": [175, 325, 223.5, 180, 1, 90], # should be off the membrane but on the coupon, used to zero the lvdt and get a baseline compression test for the coupon
        # we don't actually use test 0 anymore
        "coupon test 1": [160, 360, 223.5, 180, 1, 90],
        "coupon test 2": [170, 360, 223.5, 180, 1, 90],
        "coupon test 3": [180, 360, 223.5, 180, 1, 90],
        "coupon test 4": [150, 360, 223.5, 180, 1, 90], # only used for testing the flatness of the coupon, membrane tests only use 3 points
        "discard waypoint": [40, 250, 350, 180, 45, 90],
        "discard": [40, 250, 136, 180, 45, 90]
    }
}

ip_address = "192.168.1.198"

default_speed = 250 # mm/s
waypoint_speed = 250 # mm/s
pullcast_speed = 50 # mm/s
grab_speed = 150 # mm/s

coupon_thickness = 4.66 # mm
ring_spacing = 15 # mm
final_thickness = 8.2 # mm, thickness of the final assembly we put in the discard stack

coupon_offset = [0, 0, coupon_thickness, 0, 0, 0]
ring_offset = [-ring_spacing, 0, 0, 0, 0, 0]
discard_offset = [0, 0, final_thickness, 0, 0, 0]

# actual arm class, the whole point of this file
class Arm():
    xArm = None
    currentZone = None
    rings = 0
    coupons = 0
    discards = 0
    camera_box_open = None
    
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

    # go from current zone to destination zone, using waypoints
    # when moving to tester or opentrons, make sure to go through middle waypoint, to avoid arm crashing into back of fume hood
    def immigrate(self, destination, pitch = True):
        self.go_to(waypoints[self.currentZone], pitch=pitch)
        
        if (destination == "tester" or destination == "opentrons") and self.currentZone != "middle" and self.currentZone != destination:
            self.go_to(waypoints["middle"], speed=waypoint_speed, pitch=pitch)
        
        self.go_to(waypoints[destination], speed=waypoint_speed, pitch=pitch)
        self.currentZone = destination
    
    # simple gripper functions
    def close_gripper(self):
        self.xArm.close_bio_gripper()
        
    def open_gripper(self):
        self.xArm.open_bio_gripper()
    
    # go to named position, automatically immigrate to new zone if required
    def go_to_position(self, zone, position, speed = default_speed, pitch = True):
        if zone != self.currentZone:
            self.immigrate(zone, pitch = pitch)
        self.go_to(positions[zone][position], speed = speed)

    def go_to_position_offset(self, zone, position, offset, speed = default_speed, pitch = True):
        if zone != self.currentZone:
            self.immigrate(zone, pitch = pitch)
        self.go_to_offset(positions[zone][position], offset, speed = speed)
    
    def pick_up(self, item, pitch = True):
        item = items[item]
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
        self.go_to_position(item["home zone"], item["home position"], speed=grab_speed)
        self.close_gripper()
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
    
    def put_down(self, item, pitch = True):
        item = items[item]
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
        self.go_to_position(item["home zone"], item["home position"], speed=grab_speed)
        self.open_gripper()
        self.go_to_position(item["home zone"], item["home position"] + " waypoint", pitch = pitch)
        
    # pick up 
    
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
        
        self.put_down("knife bath")
        self.xArm.set_bio_gripper_force(100)


    # placing cap requires a special method as we need to hover the cap for some time before placing
    # but can be removed with the normal pick_up() method
    def put_cap(self, hover_time=5):
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
        self.go_to_position("opentrons", "coupon bath cap")
        self.go_to_position("opentrons", "coupon bath")
        
        self.open_gripper()
        self.go_to_position("opentrons", "coupon bath waypoint")

    # from coupon on intermediate tester stand, move to coupon test waypoint
    # used to help make protocol easier to read when doing compression tests
    def prep_coupon_test(self):
        self.go_to_position("tester", "coupon flat waypoint")
        self.go_to_position("tester", "coupon flat")
        self.close_gripper()
        self.go_to_position("tester", "coupon test 0 waypoint")
        
    def unprep_coupon_test(self):
        self.go_to_position("tester", "coupon test 0 waypoint")
        self.go_to_position("tester", "coupon flat")
        self.open_gripper()
        self.go_to_position("tester", "coupon flat waypoint")

    # when holding knife, clean with brush
    def brush_knife(self, cycles = 5):
        self.go_to_position("opentrons", "knife brush waypoint")
        
        for i in range(cycles):
            self.go_to_position("opentrons", "knife brush 1")
            self.go_to_position("opentrons", "knife brush 2")
        
        self.go_to_position("opentrons", "knife brush waypoint")
        
    # when holding knife, dry with cloth
    def dry_knife(self, cycles = 5):
        self.go_to_position("opentrons", "knife dry waypoint")
        
        for i in range(cycles):
            self.go_to_position("opentrons", "knife dry 1")
            self.go_to_position("opentrons", "knife dry 2")
        
        self.go_to_position("opentrons", "knife dry waypoint")
        
    # picking up and putting down coupons requires a special method because of the variable offset
    def pick_up_coupon(self):                                                                                  
        if self.coupons < 0:
            return
        self.coupons -= 1
        offset = [coordinate * self.coupons for coordinate in coupon_offset]
        self.go_to_position("middle", "coupon rack waypoint")
        self.go_to_position_offset("middle", "coupon rack", offset)
        self.close_gripper()
        self.go_to_position("middle", "coupon rack waypoint")
                                                                                                             
    def put_down_coupon(self):
        offset = [coordinate * self.coupons for coordinate in coupon_offset]
        self.go_to_position("middle", "coupon rack waypoint")
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
            self.immigrate("middle")
            self.open_gripper()
            self.camera_box_open = False

    def open_camera_box(self):
        if not self.camera_box_open:
            self.close_gripper()
            self.go_to_position("middle", "camera closed waypoint")
            self.go_to_position("middle", "camera closed")
            self.go_to_position("middle", "camera open")
            self.go_to_position("middle", "camera open waypoint")
            self.immigrate("middle")
            self.open_gripper()
            self.camera_box_open = True