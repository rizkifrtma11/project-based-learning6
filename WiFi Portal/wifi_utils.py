import subprocess

def scan_wifi():
    result = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"]).decode()
    networks = []
    for line in result.strip().split('\n'):
        if ':' in line:
            ssid, signal = line.split(':', 1)
            networks.append({'ssid': ssid, 'signal': signal})
    return networks

def connect_wifi(ssid, password):
    try:
        subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def forget_wifi(ssid):
    subprocess.run(["nmcli", "connection", "delete", ssid])

def current_status():
    try:
        result = subprocess.check_output(["nmcli", "-t", "-f", "ACTIVE,SSID,DEVICE,IP4.ADDRESS", "connection", "show", "--active"]).decode()
        for line in result.strip().split("\n"):
            if line.startswith("yes"):
                _, ssid, device, ip = line.split(":")
                return {"ssid": ssid, "device": device, "ip": ip}
    except:
        pass
    return {"ssid": None, "device": None, "ip": None}
