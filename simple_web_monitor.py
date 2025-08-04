#!/usr/bin/env python3
"""
Simple web dashboard for monitoring the bot.
Lightweight version that's easy to run.
"""
import http.server
import socketserver
import json
import os
import threading
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import webbrowser

class BotWebMonitor:
    """Simple HTTP server for bot monitoring."""
    
    def __init__(self, port=8888):
        self.port = port
        self.stats = {
            "balance": 0.0,
            "total_trades": 0,
            "profitable_trades": 0,
            "last_update": datetime.now().isoformat()
        }
        self.trades = []
        self.logs = []
        
    def get_wallet_balance(self):
        """Get current wallet balance."""
        try:
            # Simple balance check using public RPC
            import requests
            
            with open("config/wallet.json", 'r') as f:
                wallet_data = json.load(f)
                
            response = requests.post(
                "https://api.mainnet-beta.solana.com",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [wallet_data["public_key"]]
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    self.stats["balance"] = result["result"]["value"] / 1_000_000_000
                    
        except Exception as e:
            print(f"Error getting balance: {e}")
            
    def parse_logs(self):
        """Parse bot logs for trades."""
        try:
            log_path = "logs/pump_bot.log"
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    lines = f.readlines()[-100:]  # Last 100 lines
                    
                self.logs = []
                self.trades = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        # Add to logs
                        if " - " in line:
                            timestamp = line.split()[1] if len(line.split()) > 1 else "00:00:00"
                            message = line.split(" - ", 1)[1] if " - " in line else line
                            self.logs.append(f"[{timestamp[:8]}] {message}")
                        
                        # Parse trades
                        if "BUY executed" in line or "SELL executed" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                trade = {
                                    "time": parts[1][:8],
                                    "type": "BUY" if "BUY" in line else "SELL",
                                    "token": "Unknown",
                                    "amount": 0.001,
                                    "pnl": 0
                                }
                                
                                if "for token" in line:
                                    token_idx = line.find("for token") + 10
                                    trade["token"] = line[token_idx:token_idx+16] + "..."
                                    
                                if "Profit:" in line and "SELL" in line:
                                    try:
                                        profit_idx = line.find("Profit:") + 8
                                        trade["pnl"] = float(line[profit_idx:].split('%')[0])
                                        if trade["pnl"] > 0:
                                            self.stats["profitable_trades"] += 1
                                    except:
                                        pass
                                        
                                self.trades.append(trade)
                                
                self.stats["total_trades"] = len([t for t in self.trades if t["type"] == "BUY"])
                self.stats["last_update"] = datetime.now().isoformat()
                
        except Exception as e:
            print(f"Error parsing logs: {e}")


class MonitorRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler for the monitor."""
    
    def __init__(self, *args, monitor=None, **kwargs):
        self.monitor = monitor
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.serve_dashboard()
        elif parsed_path.path == '/api/stats':
            self.serve_stats()
        elif parsed_path.path == '/api/trades':
            self.serve_trades()
        elif parsed_path.path == '/api/logs':
            self.serve_logs()
        else:
            self.send_error(404, "Not Found")
            
    def serve_dashboard(self):
        """Serve the main dashboard HTML."""
        html = '''<!DOCTYPE html>
<html>
<head>
    <title>Solana Bot Monitor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a; color: #fff; line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; padding: 20px 0; border-bottom: 2px solid #333; margin-bottom: 20px; }
        .header h1 { font-size: 2em; color: #00d4ff; margin-bottom: 10px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; text-align: center; }
        .stat-card h3 { color: #888; font-size: 0.9em; margin-bottom: 8px; }
        .stat-card .value { font-size: 1.5em; font-weight: bold; color: #00d4ff; }
        .section { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .section h2 { color: #00d4ff; margin-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #222; color: #00d4ff; }
        .buy { color: #00ff88; }
        .sell { color: #ff3366; }
        .positive { color: #00ff88; }
        .negative { color: #ff3366; }
        .logs { background: #0a0a0a; border: 1px solid #333; border-radius: 5px; padding: 10px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 0.8em; }
        .status { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #00ff88; margin-right: 5px; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Solana Bot Monitor</h1>
            <p><span class="status"></span>Live Dashboard</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Balance</h3>
                <div class="value" id="balance">0.0000 SOL</div>
            </div>
            <div class="stat-card">
                <h3>Total Trades</h3>
                <div class="value" id="trades">0</div>
            </div>
            <div class="stat-card">
                <h3>Profitable</h3>
                <div class="value" id="profitable">0</div>
            </div>
            <div class="stat-card">
                <h3>Win Rate</h3>
                <div class="value" id="winrate">0%</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📈 Recent Trades</h2>
            <table>
                <thead>
                    <tr><th>Time</th><th>Type</th><th>Token</th><th>Amount</th><th>P&L</th></tr>
                </thead>
                <tbody id="trades-table">
                    <tr><td colspan="5" style="text-align: center; color: #666;">No trades yet...</td></tr>
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>📋 Activity Log</h2>
            <div class="logs" id="logs">Waiting for bot activity...</div>
        </div>
        
        <div style="text-align: center; padding: 20px; color: #666;">
            <p>Updates automatically every 3 seconds</p>
        </div>
    </div>
    
    <script>
        async function updateData() {
            try {
                // Update stats
                const stats = await fetch('/api/stats').then(r => r.json());
                document.getElementById('balance').textContent = stats.balance.toFixed(4) + ' SOL';
                document.getElementById('trades').textContent = stats.total_trades;
                document.getElementById('profitable').textContent = stats.profitable_trades;
                
                const winRate = stats.total_trades > 0 
                    ? (stats.profitable_trades / stats.total_trades * 100).toFixed(1)
                    : 0;
                document.getElementById('winrate').textContent = winRate + '%';
                
                // Update trades
                const trades = await fetch('/api/trades').then(r => r.json());
                const tbody = document.getElementById('trades-table');
                
                if (trades.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #666;">No trades yet...</td></tr>';
                } else {
                    tbody.innerHTML = trades.slice(0, 10).map(trade => `
                        <tr>
                            <td>${trade.time}</td>
                            <td class="${trade.type.toLowerCase()}">${trade.type}</td>
                            <td>${trade.token}</td>
                            <td>${trade.amount.toFixed(4)} SOL</td>
                            <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                                ${trade.pnl !== 0 ? (trade.pnl >= 0 ? '+' : '') + trade.pnl.toFixed(2) + '%' : '-'}
                            </td>
                        </tr>
                    `).join('');
                }
                
                // Update logs
                const logs = await fetch('/api/logs').then(r => r.json());
                const logsDiv = document.getElementById('logs');
                logsDiv.innerHTML = logs.slice(-20).join('<br>');
                logsDiv.scrollTop = logsDiv.scrollHeight;
                
            } catch (e) {
                console.error('Update error:', e);
            }
        }
        
        // Update every 3 seconds
        updateData();
        setInterval(updateData, 3000);
    </script>
</body>
</html>'''
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
        
    def serve_stats(self):
        """Serve stats JSON."""
        self.monitor.get_wallet_balance()
        self.monitor.parse_logs()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(self.monitor.stats).encode())
        
    def serve_trades(self):
        """Serve trades JSON."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(self.monitor.trades).encode())
        
    def serve_logs(self):
        """Serve logs JSON."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(self.monitor.logs).encode())


def main():
    """Start the web monitor."""
    port = 8888
    monitor = BotWebMonitor(port)
    
    # Create request handler with monitor instance
    handler = lambda *args, **kwargs: MonitorRequestHandler(*args, monitor=monitor, **kwargs)
    
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"🌐 Bot Web Monitor starting on http://localhost:{port}")
            print("📊 Dashboard will show:")
            print("   • Real-time wallet balance")
            print("   • Trade history and P&L")
            print("   • Bot activity logs")
            print("   • Trading statistics")
            print()
            print("🔗 Open this URL in your browser:")
            print(f"   http://localhost:{port}")
            print()
            print("Press Ctrl+C to stop the server")
            
            # Try to open browser automatically
            try:
                webbrowser.open(f"http://localhost:{port}")
                print("✓ Browser opened automatically")
            except:
                pass
                
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n👋 Web monitor stopped")
    except Exception as e:
        print(f"❌ Error starting web monitor: {e}")


if __name__ == "__main__":
    main()