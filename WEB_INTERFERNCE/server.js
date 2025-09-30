const express = require('express');
const path = require('path');
const app = express();
const PORT = 3000;
const { exec } = require('child_process');

// Middleware to parse JSON bodies for POST requests
app.use(express.json());

// --- Static File Serving ---
// Serve static files (index.html, style.css, script.js) from the current directory
app.use(express.static('public'));

// --- Mock Data Generator Functions ---

// Function to generate a random number between min and max (inclusive)
const randomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;


// --- API Endpoints ---

// 1. GET /dashboard-status (Summary Panel Data)
app.get('/dashboard-status', (req, res) => {
    // Fallback random summary data
    const fallbackData = {
        summary_time: `${randomInt(1, 5)} घंटे ${randomInt(0, 59)} मिनट`,
        dosage_used: `${(randomInt(10, 50) / 10).toFixed(1)} लीटर`,   // 1.0–5.0
        area_covered: `${(randomInt(10, 60) / 10).toFixed(1)} एकड़`, // 1.0–6.0
        battery_level: randomInt(30, 95)                             // 30–95%
    };

    const pythonCommand = 'python read_dashboard.py'; // Replace with your script

    exec(pythonCommand, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python execution error: ${error.message}`);
            if (stderr) console.error(`Python stderr: ${stderr}`);
            console.warn("Unable to fetch dashboard data from sensor. Displaying fallback values.");
            return res.json(fallbackData);
        }

        try {
            const dashboardData = JSON.parse(stdout);

            if (dashboardData.error) {
                console.error(`Dashboard read failed: ${dashboardData.error}`);
                console.warn("Unable to fetch dashboard data from sensor. Displaying fallback values.");
                return res.json(fallbackData);
            }

            // Success → send real sensor data
            res.json(dashboardData);
        } catch (parseError) {
            console.error("Failed to parse JSON from Python output:", stdout);
            console.warn("Unable to fetch dashboard data from sensor. Displaying fallback values.");
            res.json(fallbackData);
        }
    });
});

// 2. GET /sensor-data (Status Cards Data: Tank, Weather)
app.get('/sensor-data', (req, res) => {
    // Default fallback data
    const fallbackData = {
        tank_level: "47%",
        weather_value: "dhoop",
        weather_note: "chidkav ke liye anukool",
    };

    const pythonCommand = 'python3 sensorData.py';

    exec(pythonCommand, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python execution error: ${error.message}`);
            if (stderr) console.error(`Python stderr: ${stderr}`);
            console.warn("Unable to fetch data from sensor. Displaying fallback values.");
            return res.json(fallbackData); // fallback data
        }

        try {
            const sensorData = JSON.parse(stdout);

            if (sensorData.error) {
                console.error(`Sensor read failed: ${sensorData.error}`);
                console.warn("Unable to fetch data from sensor. Displaying fallback values.");
                return res.json(fallbackData);
            }

            // Success → send real sensor data
            res.json(sensorData);
        } catch (parseError) {
            console.error("Failed to parse JSON from Python output:", stdout);
            console.warn("Unable to fetch data from sensor. Displaying fallback values.");
            res.json(fallbackData);
        }
    });
});

// 3. POST /system-on

app.post('/system-on', (req, res) => {
    const fallbackResponse = {
        success: false,
        message: 'सिस्टम शुरू करने में विफल। कृपया पुनः प्रयास करें।',
    };

    const pythonCommand = 'python system_on.py';

    exec(pythonCommand, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python execution error: ${error.message}`);
            if (stderr) console.error(`Python stderr: ${stderr}`);
            console.warn("Unable to start system via Python script. Sending fallback response.");
            return res.json(fallbackResponse);
        }

        try {
            const result = JSON.parse(stdout);

            if (result.error) {
                console.error(`System start failed: ${result.error}`);
                console.warn("Unable to start system via Python script. Sending fallback response.");
                return res.json(fallbackResponse);
            }

            // Success → send real script response
            res.json(result);
        } catch (parseError) {
            console.error("Failed to parse JSON from Python output:", stdout);
            console.warn("Unable to start system via Python script. Sending fallback response.");
            res.json(fallbackResponse);
        }
    });
});


// 4. POST /system-off
app.post('/system-off', (req, res) => {
    const fallbackResponse = {
        success: false,
        message: 'सिस्टम बंद करने में विफल। कृपया पुनः प्रयास करें।',
    };

    const pythonCommand = 'python3 system_off.py';

    exec(pythonCommand, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python execution error: ${error.message}`);
            if (stderr) console.error(`Python stderr: ${stderr}`);
            console.warn("Unable to stop system via Python script. Sending fallback response.");
            return res.json(fallbackResponse);
        }

        try {
            const result = JSON.parse(stdout);

            if (result.error) {
                console.error(`System stop failed: ${result.error}`);
                console.warn("Unable to stop system via Python script. Sending fallback response.");
                return res.json(fallbackResponse);
            }

            res.json(result); // Success
        } catch (parseError) {
            console.error("Failed to parse JSON from Python output:", stdout);
            console.warn("Unable to stop system via Python script. Sending fallback response.");
            res.json(fallbackResponse);
        }
    });
});


// 5. POST /emergency-stop
app.post('/emergency-stop', (req, res) => {
    const fallbackResponse = {
        success: false,
        message: 'आपातकालीन रोक विफल। कृपया तुरंत मैन्युअल रूप से हस्तक्षेप करें।',
    };

    const pythonCommand = 'python3 emergency_stop.py';

    exec(pythonCommand, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python execution error: ${error.message}`);
            if (stderr) console.error(`Python stderr: ${stderr}`);
            console.warn("Unable to perform emergency stop via Python script. Sending fallback response.");
            return res.json(fallbackResponse);
        }

        try {
            const result = JSON.parse(stdout);

            if (result.error) {
                console.error(`Emergency stop failed: ${result.error}`);
                console.warn("Unable to perform emergency stop via Python script. Sending fallback response.");
                return res.json(fallbackResponse);
            }

            res.json(result); // Success
        } catch (parseError) {
            console.error("Failed to parse JSON from Python output:", stdout);
            console.warn("Unable to perform emergency stop via Python script. Sending fallback response.");
            res.json(fallbackResponse);
        }
    });
});


// --- Server Start ---
app.listen(PORT, () => {
    console.log(`✅ Server running at http://localhost:${PORT}`);
    console.log('Press Ctrl+C to stop.');
});