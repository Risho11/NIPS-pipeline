# modified to replace compressiontester functions with dummy ones
# (allows to test the rest of the system while the compression tester is non-functional)
# control nitrogen blower and compression tester via pyfirmata and the arduino

from pyfirmata import Arduino, util
import time

arduino_port = '/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_75130303036351E02061-if00'

class Uno:
    def __init__(self):
        self.board = Arduino(arduino_port)
        
        # pins for compression tester
        self.tester_output = self.board.get_pin('d:12:o') # digital pin 12 is our output, used to tell the compression tester to start
        self.tester_input = self.board.get_pin('d:9:i') # digital pin 9 is our input, used to check if the test has started & when it has finished
        self.tester_input.enable_reporting()
        # make sure output pin is high by default
        self.tester_output.write(1)
        
        # pin for N2 Blower
        self.static_blower_pin = self.board.get_pin('d:3:o') # plugged into digital pin 3 (output)
        
        # make and start iterator to keep input pin(s) up to date
        self.iterate = util.Iterator(self.board)
        self.iterate.start()

    def start_blow(self): 
        self.static_blower_pin.write(1) # open solenoid to allow N2 blowing
    
    def stop_blow(self): 
        self.static_blower_pin.write(0) # close solenoid
    
    
    def test_in(self):
        temp = self.tester_input.read()
        if temp != True and temp != False:
            print(temp)
        return temp
    
    '''
    starts test and waits until it completes
    returns 1 if tester fails to start, else returns 0 when test is complete
    of course, only works if newton tester is set up correctly
    (start on DIO1, gives logic high on DIO2 while running)
    '''
    def run_test(self): # dummy function
        # set pin low to trigger test
        #self.tester_output.write(0)
        time.sleep(5)
        #self.tester_output.write(1)
        
        print("Test has started!")
        
        # wait until test has finished
        time.sleep(60)
            
        
        # Test has finished, return 0
        print("Test complete!")
        return 0