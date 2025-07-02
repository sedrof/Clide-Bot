# Detection Speed Optimization Guide

## Current Configuration
- **Polling Interval**: 200ms (0.2 seconds)
- **Expected Detection Time**: 200-800ms
- **Location**: `src/monitoring/wallet_tracker.py` line ~96

## How to Modify Detection Speed

1. Open `src/monitoring/wallet_tracker.py`
2. Find the line: `self.POLL_INTERVAL = 0.2`
3. Change the value:
   - `0.1` = 100ms (aggressive, may hit rate limits)
   - `0.2` = 200ms (recommended for competitive trading)
   - `0.5` = 500ms (conservative, less resource intensive)
   - `1.0` = 1 second (very conservative)

## Rate Limit Considerations

### Free RPC Tiers
- **100ms polling**: ~600 requests/minute = High risk of rate limiting
- **200ms polling**: ~300 requests/minute = Moderate, usually safe
- **500ms polling**: ~120 requests/minute = Very safe

### Network Latency
- Average RPC request time: 100-300ms
- Setting polling below 200ms may not improve detection due to latency

## Performance Impact
- **CPU Usage**: Lower polling interval = higher CPU usage
- **Network**: More frequent polling = more bandwidth
- **Cost**: If using paid RPC, more requests = higher cost

## Recommended Settings by Use Case

### Competitive Trading (200ms)
```python
self.POLL_INTERVAL = 0.2  # Best balance of speed and reliability
```

### Casual Monitoring (500ms)
```python
self.POLL_INTERVAL = 0.5  # Lower resource usage
```

### Testing/Development (1s)
```python
self.POLL_INTERVAL = 1.0  # Minimal resource usage
```

## Monitoring Performance
Watch the logs for:
- "Rate limit" errors = increase interval
- "[TIMING] Transaction detected Xs after block time" = actual detection speed
- High error counts = possible rate limiting

Remember: Faster isn't always better if it causes errors!
