# control nitrogen blower, compression tester, and SHT40 sensor via pyserial
# and a custom Arduino sketch (sht40_serial_reader.ino), instead of pyfirmata.
#
# IMPORTANT: the Arduino must be flashed once (from any PC with the Arduino IDE)
# with sht40_serial_reader.ino before this will work. This script never uploads
# anything to the Arduino - it only talks to it over the serial port, which is
# all pyserial needs and all the OT-2 needs to run.

import serial
import time

arduino_port = '/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_75130303036351E02061-if00'
BAUD_RATE = 115200
timeout_time = 10


class Uno:
    def __init__(self):
        self.board = serial.Serial(arduino_port, BAUD_RATE, timeout=2)
        # give the Arduino time to reset after the serial port opens
        # (opening a serial connection resets most Arduino Unos)
        time.sleep(2)
        self.board.reset_input_buffer()

        # tester_output defaults HIGH on the Arduino side in setup(),
        # matching the original pyfirmata behavior

    def _send_command(self, cmd_char):
        self.board.write(cmd_char.encode('ascii'))
        response = self.board.readline().decode('ascii', errors='replace').strip()
        return response

    # ---------------- N2 Blower ----------------

    def start_blow(self):
        self._send_command('1')  # open solenoid to allow N2 blowing

    def stop_blow(self):
        self._send_command('0')  # close solenoid

    def start_blow_pipette(self):
        self._send_command('O')  # open solenoid to allow N2 blowing
        
    def stop_blow_pipette(self):
        self._send_command('C')  # close solenoid

    

    # ---------------- Compression Tester ----------------

    def test_in(self):
        response = self._send_command('P')
        if response == '1':
            return True
        elif response == '0':
            return False
        else:
            # some kind of error/garbage has occurred, print it out
            print(response)
            return response

    '''
    starts test and waits until it completes
    returns 1 if tester fails to start, else returns 0 when test is complete
    of course, only works if newton tester is set up correctly
    (start on DIO1, gives logic high on DIO2 while running)
    '''
    def run_test(self):
        # set pin low to trigger test
        self._send_command('L')
        time.sleep(5)
        self._send_command('H')

        # wait until input shows that test has started
        # if no signal shows up, timeout and return 1
        endTime = time.time() + timeout_time
        while (time.time() < endTime) and (not self.test_in()):
            time.sleep(0.1)

        if time.time() > endTime:
            print(f"Tester has not responded after {timeout_time} seconds, aborting.")
            return 1
        else:
            print("Test has started!")

        # wait until test has finished
        low_in_a_row = 0
        while low_in_a_row < 50:
            if self.test_in():
                low_in_a_row = 0
            else:
                low_in_a_row += 1
            time.sleep(0.1)

        print("Test complete!")
        return 0

    # ---------------- SHT40 Temp/Humidity ----------------

    def read_temp_humidity(self):
        """
        Returns (temp_C, humidity_pct) as floats, or None if the read failed.
        """
        response = self._send_command('S')
        if response.startswith("ERR"):
            print(response)
            return None
        try:
            temp_str, hum_str = response.split(",")
            air_data = {
                "temperature": temp_str,
                "humidity": hum_str
            }
            #return float(temp_str), float(hum_str)
            return air_data
        except (ValueError, AttributeError):
            print(f"Unexpected response from sensor: {response!r}")
            return None
        
    def read_2nd_temp_humidity(self):
        """
        Returns (temp_C, humidity_pct) as floats, or None if the read failed.
        """
        response = self._send_command('T')
        if response.startswith("ERR"):
            print(response)
            return None
        try:
            temp_str, hum_str = response.split(",")
            air_data = {
                "temperature": temp_str,
                "humidity": hum_str
            }
            return air_data
        except (ValueError, AttributeError):
            print(f"Unexpected response from sensor: {response!r}")
            return None

    def close(self):
        self.board.close()
