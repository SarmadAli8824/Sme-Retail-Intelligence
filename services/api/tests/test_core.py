from app.chat import validate_and_scope
def test_chat_rejects_mutation():
    try: validate_and_scope("DELETE FROM sales", "org")
    except ValueError: return
    assert False, "mutation must be rejected"
def test_chat_select_is_limited():
    assert "LIMIT 100" in validate_and_scope("SELECT sku FROM inventory", "org")
