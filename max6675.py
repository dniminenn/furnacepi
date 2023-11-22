import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)


# big bang SPI with MAX6675
# CS - chip select, SCK - clock, SO - data, UNIT - 0: Celsius, 1: Kelvin, 2: Fahrenheit
def set_pin(CS, SCK, SO, UNIT):
    global sck
    sck = SCK
    global so
    so = SO
    global unit
    unit = UNIT

    GPIO.setup(CS, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(SCK, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(SO, GPIO.IN)


# read temperature from MAX6675, CS is chip select pin
# it is normally high, when read data, it is low, can multiplex with other SPI device
def read_temp(cs_no):
    GPIO.output(cs_no, GPIO.LOW)
    time.sleep(0.002)
    GPIO.output(cs_no, GPIO.HIGH)
    time.sleep(0.22)

    GPIO.output(cs_no, GPIO.LOW)
    GPIO.output(sck, GPIO.HIGH)
    time.sleep(0.001)
    GPIO.output(sck, GPIO.LOW)
    temperature_value = 0
    for i in range(11, -1, -1):
        GPIO.output(sck, GPIO.HIGH)
        temperature_value = temperature_value + (GPIO.input(so) * (2 ** i))
        GPIO.output(sck, GPIO.LOW)

    GPIO.output(sck, GPIO.HIGH)
    error_tc = GPIO.input(so)
    GPIO.output(sck, GPIO.LOW)

    for i in range(2):
        GPIO.output(sck, GPIO.HIGH)
        time.sleep(0.001)
        GPIO.output(sck, GPIO.LOW)

    GPIO.output(cs_no, GPIO.HIGH)

    if unit == 0:
        temp = temperature_value
    if unit == 1:
        temp = temperature_value * 0.25
    if unit == 2:
        temp = temperature_value * 0.25 * 9.0 / 5.0 + 32.0

    if error_tc != 0:
        return -cs_no
    else:
        return temp


GPIO.cleanup()