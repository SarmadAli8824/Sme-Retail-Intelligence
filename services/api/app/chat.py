import re

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlglot import exp, parse_one


ALLOWED_TABLES = {
    "sales": {"date", "sku", "quantity_sold", "unit_price", "product_name", "category", "organization_id"},
    "inventory": {"sku", "stock_on_hand", "reorder_point", "product_name", "category", "unit_cost", "organization_id", "updated_at"},
    "forecasts": {"sku", "horizon_days", "model_name", "mae", "rmse", "confidence", "status", "predictions", "organization_id", "created_at"},
}
ALLOWED_FUNCTIONS = {"sum", "avg", "min", "max", "count", "coalesce", "round"}
UNSAFE_QUESTION = re.compile(r"\b(delete|drop|truncate|insert|update|alter|grant|revoke|password|secret|token)\b", re.I)


def rule_sql(question: str) -> tuple[str, str]:
    q = question.lower()
    sku_match = re.search(r"\bsku\s*(?:is|=|:|#)?\s*([a-z0-9][a-z0-9._-]{1,127})", q, re.I)
    sku_filter = f" WHERE sku = '{sku_match.group(1).upper()}'" if sku_match else ""
    if "low stock" in q or "running out" in q:
        return "SELECT sku, product_name, stock_on_hand, reorder_point FROM inventory WHERE stock_on_hand < COALESCE(reorder_point, 10) ORDER BY stock_on_hand ASC", "Items below their reorder point"
    if "stock" in q or "inventory" in q or "available" in q:
        return f"SELECT sku, product_name, stock_on_hand, reorder_point FROM inventory{sku_filter} ORDER BY stock_on_hand ASC", "Current inventory availability"
    if "forecast" in q or "demand" in q or "reorder" in q:
        return f"SELECT sku, horizon_days, model_name, confidence, mae, rmse, predictions FROM forecasts{sku_filter} ORDER BY created_at DESC", "Latest demand forecasts and reorder context"
    if "worst" in q or "bottom" in q or "slow" in q:
        return "SELECT sku, SUM(quantity_sold) AS units_sold FROM sales GROUP BY sku ORDER BY units_sold ASC", "Slowest-moving SKUs"
    if "best" in q or "top" in q or "mover" in q:
        return "SELECT sku, SUM(quantity_sold) AS units_sold FROM sales GROUP BY sku ORDER BY units_sold DESC", "Best-selling SKUs"
    return f"SELECT sku, SUM(quantity_sold) AS units_sold FROM sales{sku_filter} GROUP BY sku ORDER BY units_sold DESC", "Sales by SKU"


def validate_and_scope(sql: str, org_id: str) -> str:
    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        raise ValueError("Multiple statements are not permitted")
    tree = parse_one(cleaned, read="postgres")
    if not isinstance(tree, exp.Select) or tree.find(exp.Union) or tree.find(exp.Subquery) or tree.find(exp.With):
        raise ValueError("Only a single SELECT query is permitted")
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name not in ALLOWED_TABLES:
        raise ValueError("Query must reference one approved analytics table")
    table_name = tables[0].name
    if tree.find(exp.Star):
        raise ValueError("Wildcard selection is not permitted")
    aliases = {alias.alias for alias in tree.find_all(exp.Alias)}
    for column in tree.find_all(exp.Column):
        if column.name not in ALLOWED_TABLES[table_name] and column.name not in aliases:
            raise ValueError("Query references a prohibited column")
    for function in tree.find_all(exp.Func):
        if function.sql_name().lower() not in ALLOWED_FUNCTIONS:
            raise ValueError("Query references a prohibited function")
    prohibited = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Command)
    if any(tree.find(kind) for kind in prohibited):
        raise ValueError("Mutation is not permitted")

    alias = tables[0].alias_or_name
    tree = tree.where(exp.column("organization_id", table=alias).eq(exp.Literal.string(org_id)))
    existing_limit = tree.args.get("limit")
    if not existing_limit or int(existing_limit.expression.name) > 100:
        tree = tree.limit(100)
    return tree.sql(dialect="postgres")


def execute_safe(db: Session, scoped_sql: str, timeout_ms: int = 2000) -> list[dict]:
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text(f"SET LOCAL statement_timeout = '{int(timeout_ms)}ms'"))
    result = db.execute(text(scoped_sql))
    return [dict(row._mapping) for row in result]


def question_is_unsafe(question: str) -> bool:
    return bool(UNSAFE_QUESTION.search(question))
