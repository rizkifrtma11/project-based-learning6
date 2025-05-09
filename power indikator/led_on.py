from gpiozero import LED
from time import sleep

power_led = LED(18)

try:
    power_led.on()
    while True:
        sleep(1)
except KeyboardInterrupt:
    power_led.off()
