 function updateTemperatureData() {
  fetch('/temperature_data')
    .then(response => response.json())
    .then(data => {
      document.getElementById('flue-temperature').innerText = data.flue_temperature.toFixed(1) + '°C';
      document.getElementById('pi-temp').innerText = 'Control Board Temp: ' + data.pi_cpu_temperature.toFixed(1) + '°C';
      document.getElementById('status').innerText = data.overfire ? 'OVERFIRE CONDITION!' : 'Normal';
      document.getElementById('status').style.color = data.overfire ? '#ff4136' : '#2ecc40';
      document.getElementById('force-heat-active').innerText = data.force_heat_active ? 'Force Heat Active' : 'Force Heat Inactive';
      document.getElementById('overfire-force-shutoff-active').innerText = data.overfire_force_shutoff_active ? 'Overfire Shutoff Active' : 'Overfire Shutoff Inactive';
      document.getElementById('force-heat-on-active').innerText = data.force_heat_on_active ? 'Force Heat On Active' : 'Force Heat On Inactive';
      document.getElementById('last-polled-time').innerText = 'Last Polled: ' + data.last_polled;
    })
    .catch(error => console.error('Error:', error));
}

setInterval(updateTemperatureData, 2000); // Update every 2000 milliseconds
window.onload = updateTemperatureData; // Update on load
