# Dafinitiq AI Program Application

## Product name

SME Retail Intelligence

## Describe your AI product

Small shops often have sales and stock records in spreadsheets, but no time, budget, or technical team to turn them into useful decisions. SME Retail Intelligence lets an owner upload ordinary sales and inventory CSV files, checks and cleans the rows, then shows what is selling, what is running low, and which products may need reordering. It forecasts demand for each product and lets owners ask questions such as “Which items could run out this week?” in everyday language. The assistant can only run approved, read only queries and every result is limited to the signed in shop. It is designed for independent retailers who do not use Shopify or an ERP. I would build it with FastAPI, PostgreSQL, Next.js, Angular, Go, Prophet, and SQLGlot. For private, open model inference, I would add Ollama serving Qwen2.5 7B Instruct; the current prototype also has Gemini and Groq provider options and deterministic offline rules.

## Why did you choose this idea?

I chose this because small retailers make important buying decisions with incomplete information, even when the clues are already in their sales and stock spreadsheets. A simple CSV first tool can help them avoid missed sales from empty shelves and cash tied up in slow moving goods without forcing them to replace their existing systems. I wanted to build practical AI that gives a shop owner a clear next step, not another complicated dashboard.

## Architecture diagram

Attach [`DAFINITIQ-PRODUCT-ARCHITECTURE.mmd`](DAFINITIQ-PRODUCT-ARCHITECTURE.mmd) to the application. It is Mermaid source and can also be previewed at [mermaid.live](https://mermaid.live/).

## MVP link and access

Public interactive demo: https://sarmadali8824.github.io/Sme-Retail-Intelligence/

Access: no username or password required. The hosted demo uses fictional browser sample data so reviewers can explore the screens immediately. It does not accept or upload files, call a live model, or connect to the project database. The full backend is runnable locally with Docker and uses these seeded demo credentials:

- Email: `owner@demo.example`
- Password: `RetailDemo123!`

These credentials work with the local Docker application at `http://localhost:3000`, not with the public sample demo. The full backend is not yet deployed to a public cloud URL.

## Character requirements

- Product description: 924 characters
- Reason: 447 characters
