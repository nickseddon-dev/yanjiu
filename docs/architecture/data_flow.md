
# Data Flow

## Event Pipeline

```
X mentions ──┐
Reddit posts ┤
Polymarket  ─┼──→ data_gateway ──→ event_gateway ──→ feature_service
Onchain     ─┘                            │
                                         ↓
                    ┌────────────────────┼────────────────────┐
                    ↓                    ↓                    ↓
              HYPE features     SENTIMENT features     EXPECTATION features
                    └────────────────────┼────────────────────┘
                                         ↓
                               execution_control
                                         │
                                         ↓
                               signal_publisher
                                         │
                                         ↓
                                 signal_bridge
                                         │
                                         ↓ (HTTP POST)
                              Live Host: NautilusTrader
```

## Signal Flow

1. Social/on-chain events detected by event_gateway
2. feature_service computes feature vector
3. execution_control evaluates entry conditions
4. signal_publisher queues approved signals
5. signal_bridge delivers via HTTP with ACK/retry
6. NautilusTrader receives and executes on live host
