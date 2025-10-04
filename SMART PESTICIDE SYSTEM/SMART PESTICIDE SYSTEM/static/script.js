document.addEventListener("DOMContentLoaded", () => {
    const startBtn = document.getElementById("startBtn");
    const stopBtn = document.getElementById("stopBtn");
    const updtBtn = document.getElementById("updtdata");

    // ✅ Start Button
    startBtn.addEventListener("click", async () => {
        try {
            let res = await fetch("/start", { method: "POST" });  // ✅ no hostname
            let data = await res.json();
            alert("System Started ✅");
            console.log(data);
        } catch (err) {
            console.error("Error starting:", err);
        }
    });

    // ✅ Stop Button
    stopBtn.addEventListener("click", async () => {
        try {
            let res = await fetch("/stop", { method: "POST" });  // ✅ no hostname
            let data = await res.json();
            alert("System Stopped ⛔");
            console.log(data);
        } catch (err) {
            console.error("Error stopping:", err);
        }
    });

    // ✅ Update Data Button
    updtBtn.addEventListener("click", async () => {
        try {
            let res = await fetch("/status");   // ✅ no hostname
            let data = await res.json();
            console.log("System Status:", data);
            alert("Battery: " + data.battery + "% | Running: " + data.running);
        } catch (err) {
            console.error("Error updating:", err);
        }
    });
});