import pytest
import app as module

@pytest.fixture(autouse=True)
def reset_scheduler():
    module.scheduler=module.LeaseScheduler()
    yield

@pytest.fixture
def client():
    module.app.config["TESTING"]=True
    return module.app.test_client()

def test_health(client):
    r=client.get("/health")
    assert r.status_code==200
    assert r.get_json()["status"]=="ok"

def test_acquire_lease(client):
    r=client.post("/api/leases/job",json={"owner":"worker-1","ttl":30})
    assert r.status_code==201
    data=r.get_json()
    assert data["owner"]=="worker-1"
    assert data["token"]

def test_duplicate_acquire_rejected(client):
    client.post("/api/leases/job",json={"owner":"worker-1","ttl":30})
    r=client.post("/api/leases/job",json={"owner":"worker-2","ttl":30})
    assert r.status_code==409

def test_renew_requires_token(client):
    data=client.post("/api/leases/job",json={"owner":"worker-1","ttl":30}).get_json()
    oid=data["token"]
    assert client.post("/api/leases/job/renew",
                       headers={"Authorization":"Bearer wrong"},
                       json={"ttl":60}).status_code==403
    r=client.post("/api/leases/job/renew",
                  headers={"Authorization":f"Bearer {oid}"},
                  json={"ttl":60})
    assert r.status_code==200
    assert r.get_json()["ttl"]==60

def test_release_requires_token(client):
    data=client.post("/api/leases/job",json={"owner":"worker-1","ttl":30}).get_json()
    assert client.delete("/api/leases/job",
                         headers={"Authorization":"Bearer wrong"}).status_code==403
    r=client.delete("/api/leases/job",
                    headers={"Authorization":f"Bearer {data['token']}"})
    assert r.status_code==200
    assert client.get("/api/leases/job").status_code==404

def test_expired_lease_becomes_available(client):
    client.post("/api/leases/job",json={"owner":"worker-1","ttl":1})
    module.scheduler.leases["job"]["expires_at"]=module.monotonic()-1
    r=client.post("/api/leases/job",json={"owner":"worker-2","ttl":30})
    assert r.status_code==201
    assert r.get_json()["owner"]=="worker-2"

def test_invalid_ttl_rejected(client):
    r=client.post("/api/leases/job",json={"owner":"worker-1","ttl":0})
    assert r.status_code==400
