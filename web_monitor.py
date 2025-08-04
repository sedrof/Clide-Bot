#!/usr/bin/env python3
"""
Simple web dashboard for monitoring the bot.
Access at http://localhost:8888
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from collections import deque
import aiofiles

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web
import aiohttp_cors


class WebMonitor:
    """Web-based monitoring dashboard."""
    
    def __init__(self):
        self.app = web.Application()
        self.trades = deque(maxlen=100)
        self.logs = deque(maxlen=200)
        self.stats = {
            "balance": 0,
            "initial_balance": 0,
            "total_trades": 0,
            "profitable_trades": 0,
            "active_positions": 0,
            "total_pnl": 0,
            "last_update": datetime.now().isoformat()
        }
        self.setup_routes()
        self.setup_cors()
        
    def setup_routes(self):
        """Setup web routes."""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/stats', self.get_stats)
        self.app.router.add_get('/api/trades', self.get_trades)
        self.app.router.add_get('/api/logs', self.get_logs)
        self.app.router.add_get('/ws', self.websocket_handler)
        
    def setup_cors(self):
        """Setup CORS for API access."""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })
        
        for route in list(self.app.router.routes()):
            cors.add(route)
            
    async def index(self, request):
        """Serve the dashboard HTML."""
        html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Solana Bot Monitor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #fff;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid #333;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            color: #00d4ff;
            margin-bottom: 10px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-card h3 {
            color: #888;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #00d4ff;
        }
        .positive { color: #00ff88 !important; }
        .negative { color: #ff3366 !important; }
        .section {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section h2 {
            color: #00d4ff;
            margin-bottom: 15px;
            font-size: 1.5em;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        th {
            background: #222;
            color: #00d4ff;
            font-weight: 600;
        }
        tr:hover {
            background: #222;
        }
        .buy { color: #00ff88; }
        .sell { color: #ff3366; }
        .logs {
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .log-entry {
            margin-bottom: 5px;
            padding: 5px;
            border-left: 3px solid #333;
        }
        .log-entry.error {
            border-left-color: #ff3366;
            color: #ff6666;
        }
        .log-entry.success {
            border-left-color: #00ff88;
        }
        .log-entry.info {
            border-left-color: #00d4ff;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-indicator.active {
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        .status-indicator.inactive {
            background: #ff3366;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Solana Pump.fun Bot Monitor</h1>
            <p><span class="status-indicator active"></span>Live Dashboard</p>
        </div>
        
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <h3>Balance</h3>
                <div class="value" id="balance">0.0000 SOL</div>
            </div>
            <div class="stat-card">
                <h3>Total P&L</h3>
                <div class="value" id="pnl">+0.00%</div>
            </div>
            <div class="stat-card">
                <h3>Total Trades</h3>
                <div class="value" id="trades">0</div>
            </div>
            <div class="stat-card">
                <h3>Win Rate</h3>
                <div class="value" id="winrate">0%</div>
            </div>
            <div class="stat-card">
                <h3>Active Positions</h3>
                <div class="value" id="positions">0</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📈 Recent Trades</h2>
            <table id="trades-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Type</th>
                        <th>Token</th>
                        <th>Amount</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody id="trades-body">
                    <tr><td colspan="5" style="text-align: center; color: #666;">No trades yet...</td></tr>
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>📋 Activity Log</h2>
            <div class="logs" id="logs">
                <div class="log-entry info">Waiting for bot activity...</div>
            </div>
        </div>
    </div>
    
    <script>
        // Update stats every 2 seconds
        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                
                document.getElementById('balance').textContent = stats.balance.toFixed(4) + ' SOL';
                
                const pnl = stats.total_pnl;
                const pnlElement = document.getElementById('pnl');
                pnlElement.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '%';
                pnlElement.className = 'value ' + (pnl >= 0 ? 'positive' : 'negative');
                
                document.getElementById('trades').textContent = stats.total_trades;
                
                const winrate = stats.total_trades > 0 
                    ? (stats.profitable_trades / stats.total_trades * 100).toFixed(1)
                    : 0;
                document.getElementById('winrate').textContent = winrate + '%';
                
                document.getElementById('positions').textContent = stats.active_positions;
            } catch (e) {
                console.error('Error updating stats:', e);
            }
        }
        
        // Update trades
        async function updateTrades() {
            try {
                const response = await fetch('/api/trades');
                const trades = await response.json();
                
                const tbody = document.getElementById('trades-body');
                if (trades.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #666;">No trades yet...</td></tr>';
                    return;
                }
                
                tbody.innerHTML = trades.slice(0, 20).map(trade => `
                    <tr>
                        <td>${trade.time}</td>
                        <td class="${trade.type.toLowerCase()}">${trade.type}</td>
                        <td>${trade.token}</td>
                        <td>${trade.amount.toFixed(4)} SOL</td>
                        <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                            ${trade.pnl ? (trade.pnl >= 0 ? '+' : '') + trade.pnl.toFixed(2) + '%' : '-'}
                        </td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('Error updating trades:', e);
            }
        }
        
        // Update logs
        async function updateLogs() {
            try {
                const response = await fetch('/api/logs');
                const logs = await response.json();
                
                const logsDiv = document.getElementById('logs');
                logsDiv.innerHTML = logs.slice(0, 50).map(log => {
                    let className = 'log-entry info';
                    if (log.includes('ERROR')) className = 'log-entry error';
                    else if (log.includes('SUCCESS') || log.includes('PROFIT')) className = 'log-entry success';
                    
                    return `<div class="${className}">${log}</div>`;
                }).join('');
                
                logsDiv.scrollTop = logsDiv.scrollHeight;
            } catch (e) {
                console.error('Error updating logs:', e);
            }
        }
        
        // WebSocket for real-time updates
        let ws;
        function connectWebSocket() {
            ws = new WebSocket('ws://localhost:8888/ws');
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'update') {
                    updateStats();
                    updateTrades();
                    updateLogs();
                }
            };
            
            ws.onclose = () => {
                setTimeout(connectWebSocket, 3000);
            };
        }
        
        // Initial load and periodic updates
        updateStats();
        updateTrades();
        updateLogs();
        connectWebSocket();
        
        setInterval(updateStats, 2000);
        setInterval(updateTrades, 3000);
        setInterval(updateLogs, 2000);
    </script>
</body>
</html>
        '''
        return web.Response(text=html, content_type='text/html')
        
    async def get_stats(self, request):
        """Get current stats."""
        await self.update_stats_from_logs()
        return web.json_response(self.stats)
        
    async def get_trades(self, request):
        """Get recent trades."""
        await self.parse_trades_from_logs()
        return web.json_response(list(self.trades))
        
    async def get_logs(self, request):
        """Get recent logs."""
        await self.parse_logs()
        return web.json_response(list(self.logs)[-50:])
        
    async def websocket_handler(self, request):
        """Handle WebSocket connections."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping':
                    await ws.send_str('pong')
            elif msg.type == web.WSMsgType.ERROR:
                print(f'WebSocket error: {ws.exception()}')
                
        return ws
        
    async def update_stats_from_logs(self):
        """Update stats from log file."""
        try:
            # Get wallet balance
            with open("config/wallet.json", 'r') as f:
                wallet_data = json.load(f)
                
            # Parse logs for trades
            log_path = "logs/pump_bot.log"
            if os.path.exists(log_path):
                async with aiofiles.open(log_path, 'r') as f:
                    lines = await f.readlines()
                    
                total_trades = 0
                profitable = 0
                
                for line in lines[-1000:]:  # Last 1000 lines
                    if "BUY executed" in line:
                        total_trades += 1
                    elif "SELL executed" in line and "Profit:" in line:
                        if "Profit: +" in line:
                            profitable += 1
                            
                self.stats["total_trades"] = total_trades
                self.stats["profitable_trades"] = profitable
                
            self.stats["last_update"] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"Error updating stats: {e}")
            
    async def parse_trades_from_logs(self):
        """Parse trades from log file."""
        try:
            log_path = "logs/pump_bot.log"
            if not os.path.exists(log_path):
                return
                
            async with aiofiles.open(log_path, 'r') as f:
                lines = await f.readlines()
                
            self.trades.clear()
            
            for line in lines[-500:]:  # Last 500 lines
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
                        
                        # Extract token
                        if "for token" in line:
                            token_idx = line.find("for token") + 10
                            trade["token"] = line[token_idx:token_idx+16] + "..."
                            
                        # Extract profit for sells
                        if "Profit:" in line:
                            profit_idx = line.find("Profit:") + 8
                            try:
                                trade["pnl"] = float(line[profit_idx:].split('%')[0])
                            except:
                                pass
                                
                        self.trades.append(trade)
                        
        except Exception as e:
            print(f"Error parsing trades: {e}")
            
    async def parse_logs(self):
        """Parse recent log entries."""
        try:
            log_path = "logs/pump_bot.log"
            if not os.path.exists(log_path):
                return
                
            async with aiofiles.open(log_path, 'r') as f:
                lines = await f.readlines()
                
            self.logs.clear()
            
            for line in lines[-200:]:  # Last 200 lines
                # Clean up the line
                line = line.strip()
                if line:
                    # Format timestamp
                    if " - " in line:
                        parts = line.split(" - ", 1)
                        if len(parts) == 2:
                            timestamp = parts[0].split()[1][:8]
                            message = parts[1]
                            self.logs.append(f"[{timestamp}] {message}")
                        else:
                            self.logs.append(line)
                    else:
                        self.logs.append(line)
                        
        except Exception as e:
            print(f"Error parsing logs: {e}")
            
    async def periodic_update(self):
        """Periodically update data."""
        while True:
            await asyncio.sleep(2)
            await self.update_stats_from_logs()
            
    async def run_async(self, port=8888):
        """Run the web server asynchronously."""
        print(f"Starting web monitor on http://localhost:{port}")
        print("Open your browser to view the dashboard")
        
        # Start periodic updates
        asyncio.create_task(self.periodic_update())
        
        # Create and start the web server
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print(f"Web monitor running at http://localhost:{port}")
        print("Press Ctrl+C to stop")
        
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down web monitor...")
        finally:
            await runner.cleanup()


def main():
    """Main entry point."""
    # Check if required dependencies are installed
    try:
        import aiohttp_cors
        import aiofiles
    except ImportError as e:
        missing_module = str(e).split("'")[1]
        print(f"Installing required dependency: {missing_module}")
        os.system(f"pip install {missing_module}")
        
    monitor = WebMonitor()
    
    try:
        asyncio.run(monitor.run_async())
    except KeyboardInterrupt:
        print("\nWeb monitor stopped by user")
    except Exception as e:
        print(f"Error running web monitor: {e}")


if __name__ == "__main__":
    main()