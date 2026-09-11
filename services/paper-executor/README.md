# paper-executor

Loads an **approved, immutable** StrategySpec and submits paper orders through
TradingView (ADR-012; was Kraken demo).

Data comes from Binance and fills come from TradingView, so they are DIFFERENT
venues. Reconciliation must state which venue each number came from: a fill here
is not evidence the same fill existed in the Binance data that triggered it.

Blueprint §24, Experiment 009. Exit gate: **end-to-end demo trade + reconciliation +
kill switch.** ADR-002: paper execution is the final internship boundary — no real money.

## The loop (§24)

    market_event
       -> signal_engine.evaluate(approved_strategy)
       -> risk_engine.pre_trade_check(order_intent)
       -> execution_adapter.submit_demo_order(order_intent)
       -> reconcile(exchange_response)
       -> audit_log.append(event)

    # Any failed check => no new order.

No LLM appears anywhere in that loop. The executor never asks a model "what should I do
now?" — it evaluates rules that a human already approved.

## Non-negotiable behaviours

- Fails closed on stale data or uncertain exchange state
- Idempotency key on every submit; a retry cannot double a position
- Strategy version is fixed for the life of the deployment (change = redeploy)
- Manual pause and hard kill switch, both audited
- Reconciles its own view of positions against the exchange on every cycle

## Layout when implemented

    paper-executor/
      executor.py        # the event loop above
      signal_engine.py   # evaluates the approved spec against MarketEvents
      adapter_tradingview.py  # OrderIntent -> venue request, idempotent
      reconcile.py       # position/order state vs exchange truth
      Dockerfile
