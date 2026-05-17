# Risk Controls

Current controls:

- Fixed per-symbol sizing
- Minimum order amount validation
- Stop-loss and take-profit parameters
- Per-symbol configuration
- Runtime logging for signal and execution decisions

Recommended additions:

- Max daily loss circuit breaker
- Max open positions guard
- Slippage and spread checks
- Exchange health check before order placement
- Kill switch through environment flag or admin command
- Paper trading mode
- Position reconciliation loop
