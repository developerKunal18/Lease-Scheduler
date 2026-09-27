from time import monotonic
from threading import RLock
from uuid import uuid4
from flask import Flask, jsonify, request

app = Flask(__name__)
LOCK = RLock()
DEFAULT_TTL = 30
MIN_TTL = 1
MAX_TTL = 3600

class LeaseScheduler:
    def __init__(self):
        self.leases = {}
        self.acquisitions = 0
        self.renewals = 0
        self.releases = 0

    def expire(self, resource):
        lease = self.leases.get(resource)
        if lease and lease["expires_at"] <= monotonic():
            del self.leases[resource]
            return True
        return False

    def cleanup(self):
        for resource in list(self.leases):
            self.expire(resource)

    def acquire(self, resource, owner, ttl):
        if not resource or len(resource) > 128:
            raise ValueError("resource must contain 1-128 characters")
        if not owner or len(owner) > 128:
            raise ValueError("owner must contain 1-128 characters")
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool):
            raise ValueError("ttl must be a number")
        if ttl < MIN_TTL or ttl > MAX_TTL:
            raise ValueError(f"ttl must be between {MIN_TTL} and {MAX_TTL} seconds")
        self.expire(resource)
        if resource in self.leases:
            raise RuntimeError("resource is already leased")
        token=uuid4().hex
        now=monotonic()
        self.leases[resource]={
            "resource":resource,"owner":owner,"token":token,
            "acquired_at":now,"expires_at":now+ttl,"ttl":ttl
        }
        self.acquisitions += 1
        return self.public(self.leases[resource])

    def authorized(self, resource, token):
        self.expire(resource)
        lease=self.leases.get(resource)
        if lease is None:
            raise KeyError("lease not found")
        if not token or token != lease["token"]:
            raise PermissionError("invalid lease token")
        return lease

    def renew(self, resource, token, ttl):
        if not isinstance(ttl, (int,float)) or isinstance(ttl,bool):
            raise ValueError("ttl must be a number")
        if ttl < MIN_TTL or ttl > MAX_TTL:
            raise ValueError(f"ttl must be between {MIN_TTL} and {MAX_TTL} seconds")
        lease=self.authorized(resource,token)
        lease["expires_at"]=monotonic()+ttl
        lease["ttl"]=ttl
        self.renewals += 1
        return self.public(lease)

    def release(self, resource, token):
        self.authorized(resource,token)
        del self.leases[resource]
        self.releases += 1

    def get(self, resource):
        self.expire(resource)
        if resource not in self.leases:
            raise KeyError("lease not found")
        return self.public(self.leases[resource])

    @staticmethod
    def public(lease):
        return {
            "resource":lease["resource"],
            "owner":lease["owner"],
            "token":lease["token"],
            "ttl":lease["ttl"],
            "expires_in":round(max(0,lease["expires_at"]-monotonic()),3)
        }

    def stats(self):
        self.cleanup()
        return {"active_leases":len(self.leases),
                "acquisitions":self.acquisitions,
                "renewals":self.renewals,
                "releases":self.releases}

scheduler=LeaseScheduler()

def token():
    header=request.headers.get("Authorization","")
    return header[7:].strip() if header.startswith("Bearer ") else ""

@app.get("/health")
def health():
    with LOCK:
        scheduler.cleanup()
        return jsonify({"status":"ok","active_leases":len(scheduler.leases)})

@app.post("/api/leases/<resource>")
def acquire(resource):
    body=request.get_json(silent=True) or {}
    try:
        with LOCK:
            return jsonify(scheduler.acquire(resource,str(body.get("owner","")).strip(),
                                             body.get("ttl",DEFAULT_TTL))),201
    except RuntimeError as exc:
        return jsonify({"error":str(exc)}),409
    except ValueError as exc:
        return jsonify({"error":str(exc)}),400

@app.post("/api/leases/<resource>/renew")
def renew(resource):
    body=request.get_json(silent=True) or {}
    try:
        with LOCK:
            return jsonify(scheduler.renew(resource,token(),body.get("ttl",DEFAULT_TTL)))
    except KeyError:
        return jsonify({"error":"lease not found"}),404
    except PermissionError:
        return jsonify({"error":"invalid lease token"}),403
    except ValueError as exc:
        return jsonify({"error":str(exc)}),400

@app.delete("/api/leases/<resource>")
def release(resource):
    try:
        with LOCK:
            scheduler.release(resource,token())
        return jsonify({"resource":resource,"released":True})
    except KeyError:
        return jsonify({"error":"lease not found"}),404
    except PermissionError:
        return jsonify({"error":"invalid lease token"}),403

@app.get("/api/leases/<resource>")
def get_lease(resource):
    try:
        with LOCK:
            return jsonify(scheduler.get(resource))
    except KeyError:
        return jsonify({"error":"lease not found"}),404

@app.get("/api/leases")
def list_leases():
    with LOCK:
        scheduler.cleanup()
        leases=[scheduler.public(x) for x in scheduler.leases.values()]
    return jsonify({"leases":leases,"count":len(leases)})

@app.get("/api/stats")
def stats():
    with LOCK:
        return jsonify(scheduler.stats())

if __name__=="__main__":
    app.run(debug=True)
