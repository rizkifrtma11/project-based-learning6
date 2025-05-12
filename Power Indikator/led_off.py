from gpiozero import LED

power_led = LED(18)

# Mematikan LED dan membersihkan GPIO
power_led.off()
power_led.close()  # Membersihkan GPIO yang digunakan oleh LED
