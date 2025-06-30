# Sell Strategy Configuration Guide

## Understanding Sell Rules

Your bot uses a priority-based system to determine when to sell. Each rule has:
- **name**: A descriptive name for the rule
- **priority**: Lower numbers = higher priority (checked first)
- **conditions**: The criteria that must be met
- **action**: What to do when conditions are met (usually "DUMP_ALL")

## Current Rules Explained

### Rule 1: Quick Profit (5% in 8 seconds)
```yaml
name: "quick_profit_5pct"
conditions:
  price_gain_percent: ">= 5"
  time_seconds: "<= 8"
action: "DUMP_ALL"
```
**Meaning**: If the price goes up 5% or more within 8 seconds of buying, sell everything.

### Rule 2: Fast Exit (15% in 5 seconds)
```yaml
name: "fast_exit_15pct"
conditions:
  price_gain_percent: ">= 15"
  time_seconds: "<= 5"
action: "DUMP_ALL"
```
**Meaning**: If the price spikes 15% or more within 5 seconds, take profits immediately.

### Rule 3: Volume Spike Exit
```yaml
name: "volume_spike_exit"
conditions:
  price_gain_percent: ">= 2"
  volume_multiplier: "> 3"
action: "DUMP_ALL"
```
**Meaning**: If price is up at least 2% AND volume is 3x normal, sell (indicates potential dump incoming).

### Rule 4: Stop Loss/Timeout
```yaml
name: "timeout_stop_loss"
conditions:
  time_seconds: "> 15"
  price_gain_percent: "< 2"
action: "DUMP_ALL"
```
**Meaning**: If holding for more than 15 seconds and price gain is less than 2%, cut losses.

## How to Modify Rules

### Example 1: More Conservative Quick Profit
Change from 5% to 3%:
```yaml
conditions:
  price_gain_percent: ">= 3"  # Changed from 5
  time_seconds: "<= 8"
```

### Example 2: Longer Hold Time
Change timeout from 15 to 30 seconds:
```yaml
conditions:
  time_seconds: "> 30"  # Changed from 15
  price_gain_percent: "< 2"
```

### Example 3: Add a New Rule
Add a "moon shot" rule for extreme gains:
```yaml
- name: "moon_shot"
  conditions:
    price_gain_percent: ">= 50"
  action: "DUMP_ALL"
  priority: 0  # Highest priority
```

## Important Notes

1. **All conditions must be true**: For a rule to trigger, ALL its conditions must be met
2. **First matching rule wins**: Rules are checked in priority order
3. **Restart required**: Changes only take effect after restarting the bot
4. **Test carefully**: Start with small amounts when testing new rules
