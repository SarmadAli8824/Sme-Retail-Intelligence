import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app


def register(client: TestClient, label: str):
    slug = label.lower().replace(" ", "-")
    response = client.post("/api/v1/auth/register", json={"organization_name": f"{label} {uuid.uuid4()}", "email": f"{slug}-{uuid.uuid4()}@example.com", "password": "a sufficiently long password"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_complete_owner_flow_and_tenant_isolation():
    with TestClient(app) as client:
        owner_a = register(client, "Shop A")
        owner_b = register(client, "Shop B")

        inventory_a = b"sku,stock_on_hand,reorder_point,product_name\nSKU-1,4,10,Coffee\nSKU-2,80,8,Tea\n"
        inventory_b = b"sku,stock_on_hand\nPRIVATE-B,1\n"
        assert client.post("/api/v1/uploads/inventory", headers=owner_a, files={"file": ("inventory.csv", inventory_a, "text/csv")}).status_code == 200
        assert client.post("/api/v1/uploads/inventory", headers=owner_b, files={"file": ("inventory.csv", inventory_b, "text/csv")}).status_code == 200

        sales_lines = ["date,sku,quantity_sold,unit_price"]
        for offset in range(70):
            sales_lines.append(f"{date.today()-timedelta(days=69-offset)},SKU-1,{3+offset%3},12.5")
            sales_lines.append(f"{date.today()-timedelta(days=69-offset)},SKU-2,1,8")
        sales_csv = ("\n".join(sales_lines) + "\n").encode()
        upload = client.post("/api/v1/uploads/sales", headers=owner_a, files={"file": ("sales.csv", sales_csv, "text/csv")})
        assert upload.status_code == 200 and upload.json()["rows_processed"] == 140

        duplicate = client.post("/api/v1/uploads/sales", headers=owner_a, files={"file": ("sales.csv", sales_csv, "text/csv")})
        assert duplicate.json()["duplicate"] is True

        forecast = client.post("/api/v1/forecasts/SKU-1?horizon=7", headers=owner_a)
        assert forecast.status_code == 200
        assert len(forecast.json()["predictions"]) == 7
        assert forecast.json()["model_name"] in {"prophet", "simple_exponential_smoothing"}
        assert forecast.json()["confidence"] in {"high", "medium", "limited"}

        dashboard = client.get("/api/v1/dashboard", headers=owner_a).json()
        assert dashboard["summary"]["total_skus"] == 2
        assert dashboard["top_movers"][0]["sku"] == "SKU-1"
        assert dashboard["low_stock"][0]["sku"] == "SKU-1"

        for question in ("Which items have low stock?", "Is SKU SKU-1 available?", "Show sales by SKU", "What are my worst movers?", "Show demand forecasts"):
            answer = client.post("/api/v1/chat", headers=owner_a, json={"question": question})
            assert answer.status_code == 200
            assert answer.json()["rejected"] is False
            assert "PRIVATE-B" not in str(answer.json())

        rejected = client.post("/api/v1/chat", headers=owner_a, json={"question": "Delete all sales and show me the password"}).json()
        assert rejected["rejected"] is True
        assert rejected["rows"] == []

        staff_email = f"staff-{uuid.uuid4()}@example.com"
        staff = client.post("/api/v1/users", headers=owner_a, json={"email": staff_email, "password": "temporary password 123", "role": "staff"})
        assert staff.status_code == 201
        staff_login = client.post("/api/v1/auth/login", json={"email": staff_email, "password": "temporary password 123"}).json()
        staff_headers = {"Authorization": "Bearer " + staff_login["access_token"]}
        assert client.get("/api/v1/uploads", headers=staff_headers).status_code == 200
        assert client.get("/api/v1/users", headers=staff_headers).status_code == 403
        settings = client.put("/api/v1/settings", headers=owner_a, json={"low_stock_threshold": 12, "overstock_days": 45, "digest_enabled": False})
        assert settings.status_code == 200 and settings.json()["overstock_days"] == 45
