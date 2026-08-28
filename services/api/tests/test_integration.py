import uuid
from fastapi.testclient import TestClient
from app.main import app

def test_register_upload_and_tenant_scoped_chat():
    email=f"owner-{uuid.uuid4()}@example.com"
    with TestClient(app) as client:
        registration=client.post("/api/v1/auth/register",json={"organization_name":f"Store {uuid.uuid4()}","email":email,"password":"a sufficiently long password"})
        assert registration.status_code==200
        headers={"Authorization":"Bearer "+registration.json()["access_token"]}
        upload=client.post("/api/v1/uploads/inventory",headers=headers,files={"file":("inventory.csv",b"sku,stock_on_hand\nSKU-1,4\n","text/csv")})
        assert upload.status_code==200 and upload.json()["rows_processed"]==1
        chat=client.post("/api/v1/chat",headers=headers,json={"question":"Which items have low stock?"})
        assert chat.status_code==200
        assert chat.json()["rows"]==[{"sku":"SKU-1","stock_on_hand":4.0}]
