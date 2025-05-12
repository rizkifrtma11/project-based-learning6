from gpiozero import LED
from time import sleep
import subprocess

led = LED(17)

def is_connection_stable():
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", "8.8.8.8"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        output = result.stdout
        if "time=" in output:
            latency = float(output.split("time=")[-1].split(" ")[0])
            return latency < 200
        else:
            return False
    except:
        return False

try:
    while True:
        if is_connection_stable():
            led.off()  # stop blinking if previously blinking
            led.on()
        else:
            led.off()
            led.blink(on_time=0.2, off_time=0.2)
        sleep(2)
except KeyboardInterrupt:
    led.off()
