"""Provider boundary for schema-constrained text-to-SQL generation.

Raw provider output is always parsed/allowlisted in chat.py before it can influence a result.
The deterministic rules are retained as an offline-safe fallback for local demos.
"""
import json
import httpx
from .config import settings
SCHEMA="""Allowed PostgreSQL tables: sales(date, sku, quantity_sold, organization_id), inventory(sku, stock_on_hand, organization_id, updated_at), forecasts(sku, horizon_days, model_name, mae, rmse, organization_id, created_at). Return ONLY one SELECT statement. Never write data. Do not use organization_id; the server scopes tenants."""
async def generate_sql(question: str) -> str | None:
    prompt=f"{SCHEMA}\nQuestion: {question}"
    async with httpx.AsyncClient(timeout=12) as client:
        if settings.gemini_api_key:
            response=await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}",json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0,"maxOutputTokens":256}})
            if response.is_success:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip("`").replace("sql\n","")
        if settings.groq_api_key:
            response=await client.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {settings.groq_api_key}"},json={"model":"llama-3.1-8b-instant","messages":[{"role":"system","content":SCHEMA},{"role":"user","content":question}],"temperature":0,"max_tokens":256})
            if response.is_success: return response.json()["choices"][0]["message"]["content"].strip().strip("`").replace("sql\n","")
    return None
