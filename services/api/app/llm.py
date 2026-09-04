"""LLM provider boundary for schema-constrained text-to-SQL generation."""

import re

import httpx

from .config import settings


SCHEMA = """Allowed PostgreSQL tables:
sales(date, sku, quantity_sold, unit_price, product_name, category),
inventory(sku, stock_on_hand, reorder_point, product_name, category, unit_cost, updated_at),
forecasts(sku, horizon_days, model_name, mae, rmse, confidence, status, predictions, created_at).
Return exactly one SELECT statement using one table and approved columns. Never write data, use wildcards, query secrets, or include organization_id. The server adds tenant scope and a row limit."""


def _clean_sql(value: str) -> str:
    value = value.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", value, re.I | re.S)
    return (fenced.group(1) if fenced else value).strip().rstrip(";")


async def generate_sql(question: str) -> str | None:
    prompt = f"{SCHEMA}\nQuestion: {question}"
    async with httpx.AsyncClient(timeout=12) as client:
        if settings.gemini_api_key:
            try:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}",
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0, "maxOutputTokens": 256}},
                )
                if response.is_success:
                    return _clean_sql(response.json()["candidates"][0]["content"]["parts"][0]["text"])
            except (httpx.HTTPError, KeyError, IndexError, TypeError):
                pass
        if settings.groq_api_key:
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json={"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": SCHEMA}, {"role": "user", "content": question}], "temperature": 0, "max_tokens": 256},
                )
                if response.is_success:
                    return _clean_sql(response.json()["choices"][0]["message"]["content"])
            except (httpx.HTTPError, KeyError, IndexError, TypeError):
                pass
    return None
