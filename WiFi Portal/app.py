from flask import Flask, render_template, request, redirect, jsonify
from wifi_utils import scan_wifi, connect_wifi, current_status, forget_wifi

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan')
def scan():
    networks = scan_wifi()
    return jsonify(networks)

@app.route('/connect', methods=['POST'])
def connect():
    ssid = request.form['ssid']
    password = request.form['password']
    success = connect_wifi(ssid, password)
    return redirect('/')

@app.route('/status')
def status():
    return jsonify(current_status())

@app.route('/forget', methods=['POST'])
def forget():
    ssid = request.form['ssid']
    forget_wifi(ssid)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
