import RPi.GPIO as GPIO
import time

# big bang SPI with MAX6675
class MAX6675:
    def __init__(self, CS, SCK, SO, unit='C'):
        self.CS = CS
        self.SCK = SCK
        self.SO = SO
        self.unit = unit

        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        GPIO.setup(self.CS, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.SCK, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.SO, GPIO.IN)

    def read_temperature(self):
        self._select_chip()
        self._deselect_chip()

        self._select_chip()
        temperature_value = self._read_data()
        self._deselect_chip()

        return self._convert_temperature(temperature_value)

    def _select_chip(self):
        GPIO.output(self.CS, GPIO.LOW)
        time.sleep(0.002)

    def _deselect_chip(self):
        GPIO.output(self.CS, GPIO.HIGH)
        time.sleep(0.22)

    def _read_data(self):
        temperature_value = 0

        # Clock out the first dummy bit (D15)
        GPIO.output(self.SCK, GPIO.HIGH)
        time.sleep(0.001)
        GPIO.output(self.SCK, GPIO.LOW)
        time.sleep(0.001)

        # Read the 12-bit temperature data (D14 to D3)
        for i in range(11, -1, -1):
            GPIO.output(self.SCK, GPIO.HIGH)
            time.sleep(0.001)
            temperature_value += GPIO.input(self.SO) << i
            GPIO.output(self.SCK, GPIO.LOW)
            time.sleep(0.001)

        # Read the thermocouple error bit (D2)
        GPIO.output(self.SCK, GPIO.HIGH)
        time.sleep(0.001)
        error_tc = GPIO.input(self.SO)
        GPIO.output(self.SCK, GPIO.LOW)
        time.sleep(0.001)

        # Clock out the last two bits (D1 and D0)
        for _ in range(2):
            GPIO.output(self.SCK, GPIO.HIGH)
            time.sleep(0.001)
            GPIO.output(self.SCK, GPIO.LOW)
            time.sleep(0.001)

        # Check for thermocouple error
        if error_tc != 0:
            raise IOError("Thermocouple Error")

        return temperature_value

    def _convert_temperature(self, temperature_value):
        # Each bit increment represents 1023.75°C / 4095
        temp_celsius = temperature_value * (1023.75 / 4095)

        if self.unit == 'C':
            return temp_celsius
        elif self.unit == 'K':
            return temp_celsius + 273.15  # Convert to Kelvin
        elif self.unit == 'F':
            return temp_celsius * 9.0 / 5.0 + 32.0  # Convert to Fahrenheit
        else:
            raise ValueError("Invalid unit")