function loadNetworks() {
    fetch('/scan')
        .then(response => response.json())
        .then(data => {
            const list = document.getElementById('networkList');
            list.innerHTML = '';
            data.forEach(net => {
                const item = document.createElement('li');
                item.className = 'list-group-item';
                item.textContent = `${net.ssid} (${net.signal}%)`;
                list.appendChild(item);
            });
        });
}

function loadStatus() {
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            const statusDiv = document.getElementById('status');
            if (data.ssid) {
                statusDiv.textContent = `Terhubung ke: ${data.ssid} (${data.ip})`;
                statusDiv.className = 'alert alert-success';
            } else {
                statusDiv.textContent = "Tidak terhubung ke jaringan.";
                statusDiv.className = 'alert alert-warning';
            }
        });
}

setInterval(loadNetworks, 15000);  // auto refresh
setInterval(loadStatus, 5000);     // status refresh

loadNetworks();
loadStatus();
