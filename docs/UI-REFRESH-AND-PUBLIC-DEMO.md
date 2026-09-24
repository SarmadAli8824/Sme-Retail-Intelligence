# UI Refresh and Public Demo

Updated on 24 September 2026.

The owner app now uses a warm neutral and blue interface with separate views for overview, inventory, forecasts, assistant, and imports. Inventory search, readable answer tables, forecast dates, responsive navigation, focus states, and reduced motion support improve daily use. The Angular staff workspace uses the same visual direction.

## Public demo

The public link is https://sarmadali8824.github.io/Sme-Retail-Intelligence/.

This is an interactive browser demo with fictional sample shop data. It does not connect to the database or AI providers. Sample forecast values use a daily average and have no evaluated error metrics. Sample chat answers use local matching rules. Upload controls explain that processing requires the full application and do not transmit selected files. No login is required.

The normal Docker build uses the actual FastAPI API, PostgreSQL, forecasting models and Go worker. Full backend cloud deployment remains a future step if needed.

## Verification

- Production Next.js build and TypeScript checks passed.
- Actual Docker backend sign in, dashboard, inventory search, forecast generation and chat were checked through the browser.
- Public export navigation, inventory search, illustrative forecasts, sample chat and upload boundary were checked separately without backend access.
- A 390 pixel mobile viewport had no page overflow.
- Browser checks reported no uncaught page errors.
- The new walkthrough records interactions in the actual Docker application using an isolated fictional sample shop. The narration uses a synthetic neural voice, not a human recording.

## Restore and update

Use the main README for Docker startup. The workflow `.github/workflows/demo-pages.yml` builds and publishes the sample version. Never configure backend secrets in the public frontend. The public demo is not a replacement for full system integration tests or a production deployment.
