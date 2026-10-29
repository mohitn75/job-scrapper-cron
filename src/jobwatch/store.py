import json
import os
import threading
import time

TTL_SECONDS = 365 * 86400


class MemoryStore:
    """In-memory store (optionally persisted to a JSON file) for local runs and tests."""
    def __init__(self, path=None):
        self.path = path
        self.lock = threading.Lock()
        self.seen_set, self.states = set(), {}
        if path and os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
            self.seen_set, self.states = set(d.get("seen", [])), d.get("states", {})

    def _save(self):
        if self.path:
            with open(self.path, "w") as f:
                json.dump({"seen": sorted(self.seen_set), "states": self.states}, f)

    def seen(self, keys):
        with self.lock:
            return {k for k in keys if k in self.seen_set}

    def mark_seen(self, keys):
        with self.lock:
            self.seen_set.update(keys)
            self._save()

    def get_state(self, name):
        with self.lock:
            return json.loads(json.dumps(self.states.get(name, {})))

    def put_state(self, name, state):
        with self.lock:
            self.states[name] = json.loads(json.dumps(state))
            self._save()


class DynamoStore:
    """DynamoDB single-table store: pk = job#<company>#<id> or state#<company>."""
    def __init__(self, table):
        import boto3
        self.c = boto3.client("dynamodb")
        self.t = table

    def seen(self, keys):
        found, keys = set(), list(dict.fromkeys(keys))
        for i in range(0, len(keys), 100):
            req = {self.t: {"Keys": [{"pk": {"S": k}} for k in keys[i:i + 100]], "ProjectionExpression": "pk"}}
            tries = 0
            while req and tries < 8:
                resp = self.c.batch_get_item(RequestItems=req)
                for it in resp.get("Responses", {}).get(self.t, []):
                    found.add(it["pk"]["S"])
                req = resp.get("UnprocessedKeys") or None
                if req:
                    time.sleep(0.5 * 2 ** tries)
                    tries += 1
        return found

    def mark_seen(self, keys):
        keys = list(dict.fromkeys(keys))
        ttl = str(int(time.time()) + TTL_SECONDS)
        for i in range(0, len(keys), 25):
            req = {self.t: [{"PutRequest": {"Item": {"pk": {"S": k}, "ttl": {"N": ttl}}}} for k in keys[i:i + 25]]}
            tries = 0
            while req and tries < 8:
                resp = self.c.batch_write_item(RequestItems=req)
                req = resp.get("UnprocessedItems") or None
                if req:
                    time.sleep(0.5 * 2 ** tries)
                    tries += 1

    def get_state(self, name):
        r = self.c.get_item(TableName=self.t, Key={"pk": {"S": f"state#{name}"}})
        item = r.get("Item")
        return json.loads(item["data"]["S"]) if item else {}

    def put_state(self, name, state):
        self.c.put_item(TableName=self.t, Item={"pk": {"S": f"state#{name}"}, "data": {"S": json.dumps(state)}})
