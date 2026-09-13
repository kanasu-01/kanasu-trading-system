# Kanasu Frontend

The Kanasu frontend is a React 19, TypeScript and Vite application. It is intended to become the responsive browser control and reporting surface for V1 research and real-market-data paper trading.

## Setup and commands

From the frontend directory:

~~~powershell
npm install
npm run dev
~~~

Available package scripts:

- npm run dev — start the Vite development server.
- npm run build — run the TypeScript project build and create the Vite production bundle.
- npm run lint — run ESLint across the frontend.
- npm run preview — serve the built bundle locally for preview.

The repository currently ignores package-lock.json. Dependency reproducibility should be addressed deliberately before release; do not infer a lockfile workflow that the repository does not currently preserve.

## Current pages and components

The router currently exposes:

- / — HomePage
- /backtest — BacktestPage
- /replay — ReplayPage
- /paper — PaperTradingPage
- /portfolio — PortfolioPage

Existing supporting code includes API clients for backtest and paper routes, a lightweight-charts candle chart, trade markers/zones, SMA indicator helpers, replay controller, performance panel, navigation/layout, metric cards, decision display and shared UI controls.

Code presence does not imply that each page is connected to a validated backend workflow.

## API expectations and current limitations

The frontend expects an HTTP API under an /api base path. At this baseline, the API base URL is hard-coded in the backtest and paper API clients rather than supplied through a portable environment configuration.

Current backend behavior includes:

- backtest configuration metadata;
- a backtest run endpoint that returns a fixed mock result;
- paper start/stop/status endpoints that manage session metadata; and
- no complete API-owned feed/strategy/execution/portfolio paper lifecycle.

Replay currently loads a static JSON path. These development paths must be replaced or explicitly retained through validated contracts before the UI can be considered a complete research/paper control plane.

The backend is authoritative for strategy execution, orders, positions, cash, equity, P&L and session state. The frontend must present backend snapshots rather than reconstruct those values.

## V1 direction

The intended UI supports actual backtest and WFA jobs, dataset/source identity, reproducible results, trades/equity/drawdown/costs, real-market-data paper controls, authoritative portfolio snapshots, and clear loading/empty/error/stopped/failed states.

Desktop and mobile-browser layouts are V1 targets. Native mobile is a later horizon after APIs and responsive workflows are stable.

See [Product Vision](../docs/PRODUCT_VISION.md), [Project Status](../docs/PROJECT_STATUS.md), [Architecture](../docs/architecture/ARCHITECTURE.md), and [Paper Runtime](../docs/design/PAPER_RUNTIME.md).
