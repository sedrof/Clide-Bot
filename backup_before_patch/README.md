# Solana Pump.fun Sniping Bot

A high-performance bot for sniping new token launches on Solana's pump.fun platform. This bot monitors new token creations in real-time, evaluates trading opportunities based on configurable strategies, and executes buy/sell orders automatically.

## Features

- **Real-time Monitoring**: Connects to pump.fun WebSocket API to detect new token launches instantly
- **Price Tracking**: Continuously monitors token prices with configurable intervals
- **Volume Analysis**: Detects volume spikes that may indicate momentum
- **Strategy Engine**: Evaluates trading opportunities based on customizable rules
- **Selling Rules**: Configurable selling strategies with multiple conditions (price gain, hold time, volume)
- **Wallet Management**: Secure handling of Solana keypair and transaction signing
- **Rich Logging**: Detailed structured logging to file and console with rotation

## Project Structure

```
├── config/                 # Configuration files
│   ├── sell_strategy.yaml  # Selling strategy rules
│   ├── settings.json       # Bot settings (RPC endpoints, trading params)
│   └── wallet.json         # Wallet keypair (template)
├── logs/                   # Log files (created on run)
├── src/                    # Source code
│   ├── core/               # Core functionality
│   │   ├── connection_manager.py  # Solana RPC & WebSocket connections
│   │   ├── transaction_builder.py # Builds buy/sell transactions
│   │   └── wallet_manager.py      # Wallet operations
│   ├── monitoring/         # Monitoring components
│   │   ├── event_processor.py     # Coordinates monitoring events
│   │   ├── price_tracker.py       # Tracks token prices
│   │   ├── pump_monitor.py        # Monitors new token launches
│   │   └── volume_analyzer.py     # Analyzes trading volume
│   ├── trading/            # Trading logic
│   │   └── strategy_engine.py     # Evaluates trading strategies
│   ├── utils/              # Utility modules
│   │   ├── config.py       # Configuration management
│   │   └── logger.py       # Structured logging setup
│   └── main.py             # Main bot application
├── requirements.txt         # Python dependencies
└── README.md               # Project documentation
```

## Installation

1. **Clone Repository**:
   ```
   git clone https://github.com/yourusername/solana-pump-bot.git
   cd solana-pump-bot
   ```

2. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Configure Wallet**:
   - Edit `config/wallet.json` with your Solana keypair (64 bytes array)
   - Ensure your wallet has sufficient SOL for trading
   
4. **Customize Settings** (optional):
   - Modify `config/settings.json` for RPC endpoints, trading parameters
   - Adjust `config/sell_strategy.yaml` for custom selling rules

## Usage

Run the bot:
```
python src/main.py
```

The bot will connect to Solana RPC endpoints, monitor pump.fun for new tokens, and execute trades based on configured strategies.

## Configuration

- **Wallet**: `config/wallet.json`
  - `keypair`: Array of 64 bytes representing your Solana private key
  - `public_key`: Your wallet's public key for verification
  
- **Settings**: `config/settings.json`
  - Solana RPC & WebSocket endpoints
  - Trading parameters (max buy amount, max positions)
  - Monitoring intervals and filters
  
- **Sell Strategy**: `config/sell_strategy.yaml`
  - Configurable rules with conditions (price gain %, hold time, volume spikes)
  - Priority-based rule evaluation
  - Slippage tolerance and priority fees

## Disclaimer

This trading bot is for educational and research purposes only. Trading cryptocurrency carries significant risk, and past performance is not indicative of future results. Use at your own risk and only trade with funds you can afford to lose.

## License

MIT License - see LICENSE file for details.
