# 🚀 Solana Sniper Wallet Tracker Setup

This guide outlines a full step-by-step method to **track the best-performing sniper bot wallets** on the Solana blockchain.

---

## 📦 Requirements

- Python 3.10+
- Access to Solana RPC (preferably Helius or Shyft)
- Access to DEX APIs (Jupiter, Orca, Raydium, pumpfun)
- MongoDB or Supabase for storage
- Optional: Telegram Bot for real-time alerts

---

## 1. 🔍 Source Wallet and Trading Data

### APIs to Use:
- [Helius API](https://www.helius.xyz/)
- [Jito MEV Dashboard](https://www.jito.network/mev-dashboard)
- [Jupiter Aggregator API](https://quote-api.jup.ag/)
- [SolanaFM](https://solana.fm/) / [Solscan](https://solscan.io/)

### What to Track:
- New token liquidity creation (first pool creation)
- First swaps on those tokens
- Wallets involved in these swaps
- Timestamps, slippage, token amount in/out

---

## 2. 🧠 Define Sniper Bot Behavior

### Detection Heuristics:
- Swap within 60 seconds of first token liquidity
- Repeated rapid buy-sell behavior
- Uses high compute unit limits or priority fees
- No other wallet usage (no NFTs, no staking)

### Sample Python Logic:

```python
if tx.timestamp < token_liquidity_timestamp + 60 and tx.slippage < 0.5:
    score += 1
if txs_in_last_24h > 50 and no_nfts(wallet):
    score += 2
```

---

## 3. 💰 Backtest Wallets and Rank

- Track all trades per candidate wallet
- Estimate profit/loss per trade
- Calculate metrics:
  - ROI per trade
  - Win rate (profitable vs losing trades)
  - Avg time held
  - Total profit

Store results in a local database or Supabase table.

---

## 4. 🔄 Create Real-Time Monitor

1. Poll Jupiter/Helius for new token pools
2. Detect first buyers on new tokens
3. Append them to a watchlist
4. Track their future activity and profit

---

## 5. 🧪 Example Wallet Score Output

```json
[
  {
    "wallet": "9hAsd9Lx...B3JK",
    "roi": "134%",
    "win_rate": "73%",
    "tokens_sniped": 39,
    "avg_holding_time": "1m12s"
  }
]
```

---

## 6. 🛠️ Tools to Use

| Tool        | Purpose                      |
|-------------|------------------------------|
| Helius      | Solana decoded tx data       |
| Jito Labs   | MEV and bundle watchers      |
| Jupiter API | Track swaps + price impact   |
| Supabase    | Store and query tx data      |
| Python      | Script + logic engine        |
| MongoDB     | Local wallet database        |

---

## 7. 📲 Optional: Telegram Bot Integration

- Use Python `telebot` or `python-telegram-bot`
- Alert on profitable snipes
- Show top 10 sniper wallets updated hourly

---

## ✅ Summary

You now have a full pipeline to track sniper wallets on Solana:

1. Detect new token launches
2. Identify sniper behavior
3. Score and rank wallets
4. Monitor them in real time