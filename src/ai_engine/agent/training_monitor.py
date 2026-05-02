import json
import os
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

LOG_FILE = "./models/Raman-Qwen-Agent/training_logs.json"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RĀMAN Studio - AI Training Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f111a; color: #e2e8f0; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 15px; margin-bottom: 20px; }
        h1 { color: #a855f7; margin: 0; font-size: 24px; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; }
        .stat-value { font-size: 28px; font-weight: bold; color: #38bdf8; margin-top: 5px; }
        .stat-label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }
        .chart-container { background: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; height: 400px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Alchemist 7B Fine-Tuning Monitor</h1>
            <span id="statusBadge" style="background: #3b82f6; padding: 5px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">Loading...</span>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Current Step</div>
                <div class="stat-value" id="currentStep">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Current Loss</div>
                <div class="stat-value" id="currentLoss" style="color: #f43f5e;">0.000</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Learning Rate</div>
                <div class="stat-value" id="currentLR" style="color: #10b981;">0.000</div>
            </div>
        </div>

        <div class="chart-container">
            <canvas id="lossChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('lossChart').getContext('2d');
        const lossChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Training Loss', data: [], borderColor: '#f43f5e', backgroundColor: 'rgba(244, 63, 94, 0.1)', tension: 0.3, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { grid: { color: '#334155' } }, x: { grid: { color: '#334155' } } }, plugins: { legend: { labels: { color: '#e2e8f0' } } } }
        });

        async function fetchLogs() {
            try {
                const response = await fetch('/api/logs');
                const data = await response.json();
                
                if (data.status === 'not_started') {
                    document.getElementById('statusBadge').textContent = 'Waiting for Trainer...';
                    document.getElementById('statusBadge').style.background = '#64748b';
                    return;
                }

                document.getElementById('statusBadge').textContent = 'Training Active';
                document.getElementById('statusBadge').style.background = '#22c55e';

                const steps = data.logs.map(log => log.step);
                const losses = data.logs.map(log => log.loss);
                
                if (data.logs.length > 0) {
                    const latest = data.logs[data.logs.length - 1];
                    document.getElementById('currentStep').textContent = latest.step;
                    document.getElementById('currentLoss').textContent = latest.loss.toFixed(4);
                    document.getElementById('currentLR').textContent = latest.learning_rate.toExponential(2);
                }

                lossChart.data.labels = steps;
                lossChart.data.datasets[0].data = losses;
                lossChart.update();
                
            } catch (error) {
                console.error("Error fetching logs:", error);
            }
        }

        setInterval(fetchLogs, 2000); // Poll every 2 seconds
        fetchLogs();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/logs")
def get_logs():
    if not os.path.exists(LOG_FILE):
        return jsonify({"status": "not_started", "logs": []})
    
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
        return jsonify({"status": "running", "logs": logs})
    except json.JSONDecodeError:
        return jsonify({"status": "running", "logs": []})

if __name__ == "__main__":
    print("🚀 Monitoring Dashboard running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
