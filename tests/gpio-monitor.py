import RPi.GPIO as GPIO
import time

# Clean up any previous configurations
try:
    GPIO.cleanup()
except:
    pass

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

# Use GPIO 10 and GPIO 4
button1_pin = 10
button2_pin = 4  # Physical pin 7

# Setup pins
GPIO.setup(button1_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(button2_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

print(f"Monitoring GPIO pins {button1_pin} and {button2_pin}. Press Ctrl+C to exit.")
try:
    while True:
        state1 = GPIO.input(button1_pin)
        state2 = GPIO.input(button2_pin)
        print(f"GPIO{button1_pin}: {state1}  GPIO{button2_pin}: {state2}", end="\r")
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
    print("\nExiting...")
finally:
    # Make sure we clean up GPIO resources even if there's an error
    GPIO.cleanup()
