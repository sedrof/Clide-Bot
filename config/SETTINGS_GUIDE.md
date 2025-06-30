# Settings Configuration Guide

## Trading Section
- **max_positions**: Maximum number of tokens you can hold at once (default: 5)
- **max_buy_amount_sol**: Maximum SOL to spend per trade (default: 0.1)
  - This is your "bet size limiter"
  - Bot will never spend more than this amount on a single trade
  - If tracked wallet buys with 1 SOL, bot only uses max_buy_amount_sol

## Monitoring Section
- **new_token_check_interval**: How often to check for new tokens (seconds)
- **price_check_interval**: How often to update token prices (seconds)
- **volume_check_interval**: How often to check volume changes (seconds)
- **max_token_age_minutes**: Ignore tokens older than this (minutes)
- **min_market_cap**: Minimum market cap to consider buying ($)
- **volume_spike_threshold**: Volume multiplier to trigger sell (e.g., 3.0 = 3x normal)

## To Change Max Buy Amount:
1. Open config/settings.json
2. Find "max_buy_amount_sol" under "trading"
3. Change the value (e.g., 0.05 for 0.05 SOL max)
4. Save and restart the bot

## To Edit Sell Rules:
1. Open config/sell_strategy.yaml
2. Modify the conditions for each rule
3. Add new rules or remove existing ones
4. Save and restart the bot

## Example Settings Change:
```json
"trading": {
    "max_positions": 5,
    "max_buy_amount_sol": 0.05  // Changed from 0.1 to 0.05
}
```
