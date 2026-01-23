# EdgeX High-Frequency Bot (Variational Hedging + Grid)

## Overview
This repository contains strategy modules for an EdgeX-based high‑frequency trading system. It combines:

- **Grid market‑making** to harvest short‑term volatility on selected symbols.
- **Variational hedging** to control net exposure and sustain trading volume on core symbols.

The code here is **not a standalone application**. It is a set of Spring components that must be integrated into the larger trading platform (Spring Boot runtime, Redis, database mappers, and EdgeX API clients).

## Strategy Composition
The orchestrator is `StrategyManager`, which schedules both strategies in a single loop:

- **Grid strategy**: `HighFrequencyMarketMakingStrategyV38Service`
  - Runs on **SOL + GRID-04/05/06** by default.
  - Builds multi‑level buy/sell grids based on configurable spacing and depth.
  - Tracks pending orders and positions in Redis.

- **Variational hedging strategy**: `VariationalHedgingStrategyV38Service`
  - Runs on **BTC/ETH** by default.
  - Monitors net exposure across the hedge symbols and places offsetting orders when exposure exceeds a threshold.
  - In normal state (exposure within limits), it places paired buy/sell orders at **best bid/ask** to promote fills.

These symbol sets are **separated** by default, so Redis state does not collide as long as symbols do not overlap.

## Default Symbol Split
Defined in `StrategyManager`:

- **Grid symbols**: `10000003`, `10000004`, `10000005`, `10000006`
- **Hedge symbols**: `10000001`, `10000002`

If you change these lists, avoid overlapping contract IDs unless you intentionally want shared Redis state.

## Key Parameters (GridStrategyConfig)
- `gridLevels`: number of price levels per side (default: 3)
- `gridSpacingPct`: spacing between levels (default: 0.8%)
- `positionSizePct`: grid order sizing (default: 9% of balance)
- `hedgeOrderSizePct`: hedge order sizing (default: 1% of balance)
- `maxPositionPerSide`: position count cap per side
- `orderRefreshInterval`, `minOrderInterval`, `apiCallInterval`

## Redis State Model
State is stored per **account + contract** using the key prefix:

```
grid:strategy:{accountId}:{contractId}:{suffix}
```

This includes:
- Pending order hash
- Buy/Sell grid lists
- Net position and long/short counters
- Last order timestamp

As long as each contract is exclusive to one strategy, the state remains isolated.

## Execution Flow (High Level)
1. Scheduler queries active accounts.
2. Grid strategy refreshes grids when price deviates or orders are depleted.
3. Hedging strategy computes net exposure on hedge symbols.
   - If exposure exceeds threshold, it places a hedge order.
   - Otherwise, it runs normal grid placement on hedge symbols.
4. Both strategies reconcile fills and update Redis state.

## External Dependencies
This repo relies on external platform components, including:

- Spring (`@Component`, DI)
- Redis (`StringRedisTemplate`)
- DB mappers (`AccountKeyMapper`, `OrderMapper`, `ThirdContractMapper`)
- EdgeX API client (`EdgeXApiClient`)
- Shared domain classes under `com.tradez.*`

It will not compile or run by itself without the full platform.

## Safety Notes
- Avoid running both strategies on the **same contract ID** unless you intend to share state.
- Enforce correct API rate limits using `apiCallInterval` and `minOrderInterval`.
- Position and exposure controls are enforced via Redis‑tracked counters, not via direct exchange position queries.

## How to Integrate
1. Place these modules into the main Spring project with required dependencies.
2. Ensure Redis and database connectivity are configured.
3. Wire `StrategyManager.start()` from a controller or startup hook.
4. Verify contract lists and risk parameters for your deployment.

## File Map
- `StrategyManager.java`: scheduler + contract split
- `HighFrequencyMarketMakingStrategyV38Service.java`: grid logic
- `VariationalHedgingStrategyV38Service.java`: hedge logic
- `SymbolGridManager.java`: Redis state tracking
- `EdgeXClient.java` / `EdgeXClientImpl.java`: exchange API adapter
- `GridStrategyConfig.java`: parameters and models
- `JsonUtil.java`: Redis serialization helper

## License
No license file is included. All usage should comply with the owning organization’s policies.
