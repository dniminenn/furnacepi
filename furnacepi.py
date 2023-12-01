from flask import Flask, render_template, jsonify
import RPi.GPIO as GPIO
from max6675 import MAX6675
import time
from threading import Thread, Lock
import subprocess
import logging
from datetime import datetime

# FOR THIS CIRCUIT,
# RELAY "FORCE HEAT" SHORTS W TO R (parallel), CLOSEST TO PI
# RELAY "OVERFIRE" SHUTOFF OPENS W (series), CLOSEST TO FURNACE
# The order of connections is important for safety, if the force heat relay fails, the overfire shutoff relay will
# still be able to shut off the furnace.  If the overfire shutoff relay fails closed, the thermostat will still
# be able to shut off the furnace.

# Physical GPIO pin numbers
OVERFIRE_FORCE_SHUTOFF_PIN = 15  # K1 NC
FORCE_HEAT_ON_PIN = 7  # K2 NO
PUSH_BUTTON_PIN = 13

# MAX6675 setup with physical GPIO pin numbers
CS_PIN = 22
SCK_PIN = 18
SO_PIN = 16
UNITS = 'C'

# Temperature thresholds, CAUTION: these are unique to my furnace and probe, set up your own thresholds
TEMP_STARTUP_HIGH = 175  # wood loaded, taper off this temp
TEMP_STARTUP_LOW = 165  # starting up, bounce from this temp
TEMP_THRESHOLD_HIGH = 245
TEMP_THRESHOLD_MIDDLE = 180
TEMP_THRESHOLD_LOW = 115

# Startup bounce cycles, how many times to bounce between startup high and low
STARTUP_BOUNCE_CYCLES = 1

# Debounce time in milliseconds for the startup button
DEBOUNCE_TIME = 500

# Global variables
overfire_condition = False
force_heat_active = False
startup_active = False
startup_bounce_count = 0
button_pressed = False

temperature_lock = Lock()
current_temperature = None
last_poll_time = None

ForceHeat = None
OverfireShutoff = None

# Flask app setup
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

# Relay control class
class RelayControl:
    def __init__(self, pin, initial_state=GPIO.HIGH):
        self.pin = pin
        GPIO.setup(self.pin, GPIO.OUT, initial=initial_state)

    def on(self):
        GPIO.output(self.pin, GPIO.LOW)

    def off(self):
        GPIO.output(self.pin, GPIO.HIGH)

    def is_active(self):
        return is_relay_active(self.pin)


# Initialize GPIO, read max6675.py for details
def initialize_gpio():
    GPIO.setmode(GPIO.BOARD)  # Use physical pin numbering
    GPIO.setup(OVERFIRE_FORCE_SHUTOFF_PIN, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(FORCE_HEAT_ON_PIN, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(PUSH_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(PUSH_BUTTON_PIN, GPIO.RISING, callback=button_callback, bouncetime=DEBOUNCE_TIME)

    global ForceHeat, OverfireShutoff
    ForceHeat = RelayControl(FORCE_HEAT_ON_PIN)
    OverfireShutoff = RelayControl(OVERFIRE_FORCE_SHUTOFF_PIN)


# interrupt callback for startup button, set global variable
def button_callback(channel):
    # important to stick a 0.1uF capacitor between the switch terminals, the rpi library
    # doesn't actually debnc the switch, it just ignores further events for bouncetime
    log.warning("Button pressed")
    global button_pressed
    button_pressed = True


# sanity check for relay state
def is_relay_active(pin):
    return GPIO.input(pin) == GPIO.LOW


sensor = MAX6675(CS_PIN, SCK_PIN, SO_PIN, UNITS)


# Poll temperature, this is kept in a separate thread to avoid blocking the main thread
def poll_temperature():
    log.info("Starting temperature polling thread...")
    global current_temperature, last_poll_time
    while True:
        temperatures = []
        for _ in range(3):
            try:
                temp = sensor.read_temperature()  # Use the MAX6675 class method
            except IOError as e:
                log.error(f"Error reading temperature: {e}")
                continue

            temperatures.append(temp)
            time.sleep(0.1)  # Sleep between polls

        with temperature_lock:  # Ensure thread-safe updates to the global variable
            if temperatures:
                current_temperature = round(sum(temperatures) / len(temperatures), 1)
            else:
                current_temperature = None
            last_poll_time = datetime.now()

        time.sleep(0.1)


# Read temperature from the global variable, thread-safe
def read_temperature():
    with temperature_lock:
        return current_temperature


# Flask endpoint to get temperature data, raw JSON
@app.route('/temperature_data')
def temperature_data():
    flue_temperature = read_temperature()
    pi_cpu_temperature = get_pi_cpu_temperature()
    last_polled = last_poll_time.strftime('%Y-%m-%d %H:%M:%S') if last_poll_time else "Not yet polled"

    return jsonify(
        flue_temperature=flue_temperature,
        pi_cpu_temperature=pi_cpu_temperature,
        overfire=overfire_condition,
        force_heat_active=force_heat_active,
        overfire_force_shutoff_active=OverfireShutoff.is_active(),
        force_heat_on_active=ForceHeat.is_active(),
        last_polled=last_polled,
        startup_active=startup_active,
        button_pressed=button_pressed,
        startup_bounce_count=startup_bounce_count
    )


def run_flask_app():
    #print("Starting Flask app on a separate thread...")
    app.run(host='0.0.0.0', port=5000)


# Function to get Raspberry Pi's CPU temperature
def get_pi_cpu_temperature():
    try:
        result = subprocess.run(['vcgencmd', 'measure_temp'], stdout=subprocess.PIPE)
        output = result.stdout.decode('utf-8').strip()
        # Extract just the temperature number
        temp_str = output.replace("temp=", "").replace("'C", "")
        return temp_str
    except Exception as e:
        print(f"Error getting Pi temperature: {e}")
        return "Error"


@app.route('/')
def index():
    return render_template('index.html')


# This is fugly, probably organize control logic better but safety first, overfire takes priority
if __name__ == "__main__":
    #print('\033[1;32m' + "Starting furnace monitor..." + '\033[0m')
    # GPIO initialization
    initialize_gpio()
    #print('\033[1;32m' + "GPIO initialized." + '\033[0m')
    # Start the temperature polling thread
    temperature_thread = Thread(target=poll_temperature)
    temperature_thread.daemon = True  # Daemonize thread
    temperature_thread.start()
    # Start the Flask app in a separate thread
    flask_thread = Thread(target=run_flask_app)
    flask_thread.daemon = True  # Daemonize thread
    flask_thread.start()

    try:
        log.warning('\033[1;32m' + "Furnace controller started" + '\033[0m')
        while True:
            with temperature_lock:  # Use the lock to safely access current_temperature
                if current_temperature is not None:
                    if current_temperature >= TEMP_THRESHOLD_HIGH:
                        OverfireShutoff.on()
                        overfire_condition = True
                        startup_bounce_count = 0
                        startup_active = False
                        button_pressed = False
                    elif overfire_condition and current_temperature <= TEMP_THRESHOLD_MIDDLE:
                        OverfireShutoff.off()
                        overfire_condition = False
                    # Handle startup mode
                    elif button_pressed:
                        if not startup_active:
                            ForceHeat.on()
                            force_heat_active = False
                            startup_active = True
                            startup_bounce_count = 0
                        elif startup_active and startup_bounce_count < STARTUP_BOUNCE_CYCLES:
                            if current_temperature >= TEMP_STARTUP_HIGH:
                                startup_bounce_count += 1
                                ForceHeat.off()
                            elif current_temperature <= TEMP_STARTUP_LOW:
                                ForceHeat.on()
                        else:
                            startup_bounce_count = 0
                            startup_active = False
                            button_pressed = False
                    # Normal operation
                    elif current_temperature < TEMP_THRESHOLD_LOW and not force_heat_active:
                        ForceHeat.on()
                        force_heat_active = True
                    elif force_heat_active and current_temperature >= TEMP_THRESHOLD_LOW + 15:
                        ForceHeat.off()
                        force_heat_active = False
            time.sleep(2)  # Polling delay
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()  # Clean up GPIO on exit
