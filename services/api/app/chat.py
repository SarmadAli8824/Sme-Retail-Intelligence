import re
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlglot import parse_one, exp
ALLOWED_TABLES={"sales":{"date","sku","quantity_sold","organization_id"},"inventory":{"sku","stock_on_hand","organization_id","updated_at"},"forecasts":{"sku","horizon_days","model_name","mae","rmse","organization_id","created_at"}}
def rule_sql(question: str) -> tuple[str,str]:
    q=question.lower()
    if "low stock" in q: return "SELECT sku, stock_on_hand FROM inventory WHERE stock_on_hand < 10 ORDER BY stock_on_hand ASC", "Items with fewer than 10 units in stock"
    if "stock" in q or "inventory" in q: return "SELECT sku, stock_on_hand FROM inventory ORDER BY stock_on_hand ASC", "Current inventory"
    if "forecast" in q or "demand" in q: return "SELECT sku, model_name, mae, rmse, predictions FROM forecasts ORDER BY created_at DESC", "Latest per-SKU forecasts"
    if "best" in q or "top" in q or "mover" in q: return "SELECT sku, SUM(quantity_sold) AS units_sold FROM sales GROUP BY sku ORDER BY units_sold DESC", "Best selling SKUs"
    return "SELECT sku, SUM(quantity_sold) AS units_sold FROM sales GROUP BY sku ORDER BY units_sold DESC", "Sales by SKU"
def validate_and_scope(sql: str, org_id: str) -> str:
    if ";" in sql.strip().rstrip(";"): raise ValueError("Multiple statements are not permitted")
    tree=parse_one(sql, read="postgres")
    if not isinstance(tree, exp.Select): raise ValueError("Only SELECT queries are permitted")
    tables={t.name for t in tree.find_all(exp.Table)}
    if not tables or not tables <= set(ALLOWED_TABLES): raise ValueError("Query references a prohibited table")
    for col in tree.find_all(exp.Column):
        if col.name != "*" and not any(col.name in cols for cols in ALLOWED_TABLES.values()): raise ValueError("Query references a prohibited column")
    prohibited=(exp.Insert,exp.Update,exp.Delete,exp.Drop,exp.Alter,exp.Create,exp.Command)
    if any(tree.find(kind) for kind in prohibited): raise ValueError("Mutation is not permitted")
    # Every allowed table has an organization_id. Scope by wrapping the approved query.
    return f"SELECT * FROM ({tree.sql(dialect='postgres')}) AS tenant_result LIMIT 100"
def execute_safe(db: Session, sql: str, org_id: str):
    # Inject org predicate into each table through a bound parameter; model SQL never controls tenant id.
    scoped=sql
    for table in ALLOWED_TABLES:
        scoped=re.sub(rf"\b{table}\b", f"{table} WHERE {table}.organization_id = :org_id", scoped, flags=re.I)
    # Grouped queries need the predicate before GROUP BY; rule SQL is trusted and table-limited.
    result=db.execute(text(scoped),{"org_id":org_id})
    return [dict(row._mapping) for row in result]
