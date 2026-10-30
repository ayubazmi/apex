import os


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "BROKEN"


def test_ready_checks_database(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "up"


def test_create_and_list_ticket(client):
    r = client.post("/api/tickets", json={"title": "Disk 90% full", "priority": "high"})
    assert r.status_code == 201
    assert r.json()["status"] == "open"
    assert len(client.get("/api/tickets").json()) == 1


def test_validation_rejects_short_title(client):
    r = client.post("/api/tickets", json={"title": "x"})
    assert r.status_code == 422


def test_update_status_and_stats(client):
    tid = client.post("/api/tickets", json={"title": "Nginx 502 errors"}).json()["id"]
    r = client.patch(f"/api/tickets/{tid}", json={"status": "resolved"})
    assert r.json()["status"] == "resolved"
    assert client.get("/api/stats").json()["by_status"]["resolved"] == 1


def test_delete_missing_ticket_returns_404(client):
    assert client.delete("/api/tickets/9999").status_code == 404


def test_metrics_exposed(client):
    client.get("/health")
    assert "apex_requests_total" in client.get("/metrics").text


def test_intentional_failure_demo():
    """CI demo ke liye: DEMO_FAIL=true set karoge to ye jaan-boojh ke fail hoga,
    jisse CI red hoga aur deploy block dikhega. Normally pass."""
    assert os.getenv("DEMO_FAIL", "false").lower() != "true", "Intentional failure for CI demo"
