from ika.chiller import Chiller
import time

chiller_port = "/dev/serial/by-id/usb-STMicroelectronics_STM32_Virtual_ComPort-if00"

epsilon = 0.1 # accetable error in temperature
timestep = 10

class BathChiller():
    chiller = None
    
    def __init__(self):
        self.chiller = Chiller(port = chiller_port)
        self.chiller.set_watchdog_safety_temperature(10)
        self.chiller.start_heating()

    def turn_off(self):
            self.chiller.stop_heating()
        
    def turn_on(self):
        self.chiller.start_heating()
    
    def get_temperature(self):
        return self.chiller.temperature()
    
    def get_target_temperature(self):
        return self.chiller.target_temperature()

    def set_target_temperature(self, temperature):
        self.chiller.set_target_temperature(temperature)
        return self.chiller.target_temperature()
    
    def go_to_temperature(self, temperature):
        self.set_target_temperature(temperature)
        self.chiller.start_heating()
        
        if self.get_target_temperature() != temperature:
            print("Chiller not responding")
            return 1
        
        current_temperature = self.get_temperature()
        
        while (current_temperature <= (temperature - epsilon)) or (current_temperature >= (temperature + epsilon)):
            print(f"Current bath temperature: {current_temperature} C")
            time.sleep(timestep)
            current_temperature = self.get_temperature()

        print(f"Reached target temperature of {temperature}.")

        return 0
    
    