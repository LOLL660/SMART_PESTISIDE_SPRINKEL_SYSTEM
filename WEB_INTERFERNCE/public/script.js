
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const emergencyBtn = document.querySelector('.btn-emergency');
    const updtdata = document.getElementById('updtdata');


    const sprayerStatus = document.querySelector('.sprayer-status');
    const sprayerIcon = document.querySelector('.sprayer-icon');
    const systemStatusValue = document.querySelector('.system-status .status-value');
    const systemStatusIcon = document.querySelector('.system-status .status-icon');
    



    
async function fetchDashboardMetrics() {
    try {
        const response = await fetch('/dashboard-status'); // Single call
        const data = await response.json();
        
        // Function to update all status cards at once
        updateDashboardUI(data); 
    } catch (error) {
        alert("dashboard ka डेटाबेस से डेटा लोड नहीं हो पा रहा है");
    }
}




async function fetchSensorData() {
    try {
        const response = await fetch('/sensor-data'); // Single call
        const data = await response.json();
        
        // Function to update all status cards at once
        updateSensorData(data); 
    } catch (error) {
        alert("sensors ka डेटाबेस से डेटा लोड नहीं हो पा रहा है");
    }
}



    async function onsystem() {
        try {
            // Using a POST request to signal a state change
            const response = await fetch('/system-on', { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                alert(`छिड़काव शुरू किया गया! Backend message: ${data.message || 'System ON'}`);
                updateStatus(true); // Update frontend UI to ON state
            } else {
                // Handle non-200 responses (e.g., 400, 500)
                alert(`Error starting system: ${data.error || response.statusText}`);
            }
        } catch (error) {
            console.error('API Error (onsystem):', error);
            alert("सिस्टम बैकएंड से कनेक्ट नहीं हो पा रहा है");
        }
    }

    /**
     * Sends request to turn the system OFF and stop spraying.
     */
    async function ofsystem() {
        try {
            const response = await fetch('/system-off', { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                alert(`छिड़काव बंद किया गया! Backend message: ${data.message || 'System OFF'}`);
                updateStatus(false); // Update frontend UI to OFF state
            } else {
                alert(`Error stopping system: ${data.error || response.statusText}`);
            }
        } catch (error) {
            console.error('API Error (ofsystem):', error);
            alert("सिस्टम बैकएंड से कनेक्ट नहीं हो पा रहा है");
        }
    }

    /**
     * Sends request for a critical emergency shutdown.
     */
    async function emergencystop() {
        const confirmStop = confirm("क्या आप आपातकालीन रोक लगाना चाहते हैं? यह पूरी तरह से सिस्टम को बंद कर देगा।");
        
        if (!confirmStop) return; // Exit if user cancels the confirmation

        try {
            const response = await fetch('/emergency-stop', { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                alert(`आपातकालीन रोक सक्रिय! सिस्टम बंद। Backend message: ${data.message || 'EMERGENCY STOP'}`);
                
                // Critical UI update after successful stop
                systemStatusValue.textContent = 'बंद'; // System status goes to 'बंद' (Stopped)
                systemStatusIcon.textContent = '✖';
                systemStatusValue.style.color = 'var(--primary-red)';
                systemStatusIcon.style.color = 'var(--primary-red)';
                updateStatus(false); // Ensure sprayer status is also off
            } else {
                alert(`Emergency Stop Error: ${data.error || response.statusText}`);
            }
        } catch (error) {
            console.error('API Error (emergencystop):', error);
            alert("सिस्टम बैकएंड से कनेक्ट नहीं हो पा रहा है");
        }
    }




function updateSensorData(data){
      var levelValue= document.querySelector('.level-value');
      var StatusValue = document.querySelector('.weather-value');
      var weatherNote = document.querySelector('.weather-note');

      levelValue.textContent = data.tank_level;
      StatusValue.textContent = data.weather_value;
      weatherNote.textContent = data.weather_note;

      // Optionally, update the progress bar width too
      var progressBar = document.querySelector('.progress-bar');
      progressBar.style.width = data.tank_level; // Sync with level valu

}



function updateDashboardUI(data) {
    // Select the summary panel
    var summaryPanel = document.querySelector('.summary-panel');
    
    if (!summaryPanel) return; // safety check

    // Get all the summary items inside it
    var summaryItems = summaryPanel.querySelectorAll('.summary-item');

    // Map JSON data keys to the order of summary items in HTML
    var newValues = [
        data.summary_time,
        data.dosage_used,
        data.area_covered,
        data.battery_level + " % 🔋"
    ];

    // Loop through each item and update the second <p>
    for (var i = 0; i < summaryItems.length; i++) {
        var paragraphs = summaryItems[i].getElementsByTagName('p');
        if (paragraphs.length >= 2) {
            paragraphs[1].textContent = newValues[i];
        }
    }
}


    // Function to update system status display
    function updateStatus(isSpraying) {
        if (isSpraying) {
            sprayerStatus.textContent = 'छिड़काव चालू';
            systemStatusValue.textContent = 'चालू';
            systemStatusValue.classList.add('active');
            systemStatusIcon.classList.add('active');
        } else {
            sprayerStatus.textContent = 'छिड़काव बंद';
            systemStatusValue.textContent = 'बंद'; // Keeping system 'चालू' as it's running but not spraying
        }
    }
    
    // Event Listeners
    startBtn.addEventListener('click', () => {
        onsystem();
    });

    stopBtn.addEventListener('click', () => {
        ofsystem();
    });

    emergencyBtn.addEventListener('click', () => {
            emergencystop();
    });
    updtdata.addEventListener('click', () => {
        fetchDashboardMetrics();
        fetchSensorData();
    });
