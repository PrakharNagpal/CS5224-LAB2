import json
import os

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("TABLE_NAME", "twitter_counts")
MAX_BATCH = 25
MAX_SAMPLE = 100

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)

CORS = {
    "Content-Type": "application/json",
}


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": CORS, "body": json.dumps(body)}


def _fetch_one(user_id: str):
    item = _table.get_item(Key={"user_id": user_id}).get("Item")
    if not item:
        return None
    return {
        "user_id": item["user_id"],
        "followers": int(item["followers"]),
        "followees": int(item["followees"]),
    }


def _fetch_many(user_ids):
    keys = [{"user_id": u} for u in user_ids]
    resp = _dynamodb.batch_get_item(RequestItems={TABLE_NAME: {"Keys": keys}})
    found = {
        i["user_id"]: {
            "user_id": i["user_id"],
            "followers": int(i["followers"]),
            "followees": int(i["followees"]),
        }
        for i in resp["Responses"].get(TABLE_NAME, [])
    }
    # preserve the caller's order, report misses explicitly
    return [found.get(u, {"user_id": u, "error": "not found"}) for u in user_ids]


def _fetch_sample(limit: int):
    """Return a page of users so the front-end can browse the dataset.

    Scan is acceptable here because the page size is small and bounded; it is
    never used to serve a per-user lookup, which always goes through GetItem.
    """
    resp = _table.scan(Limit=limit)
    rows = [
        {
            "user_id": i["user_id"],
            "followers": int(i["followers"]),
            "followees": int(i["followees"]),
        }
        for i in resp.get("Items", [])
    ]
    rows.sort(key=lambda r: int(r["user_id"]))
    return rows


def lambda_handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "GET")
    path = http.get("path", "/")
    params = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    try:
        if path == "/" or path == "":
            return _response(200, {
                "service": "cs5224-lab2-backend",
                "table": TABLE_NAME,
                "usage": ["/user/{id}", "/users?ids=a,b,c", "/sample?limit=20"],
            })

        if path.startswith("/user/"):
            user_id = path[len("/user/"):].strip()
            if not user_id.isdigit():
                return _response(400, {"error": "user id must be numeric"})
            result = _fetch_one(user_id)
            if result is None:
                return _response(404, {"error": f"user {user_id} not found"})
            return _response(200, result)

        if path == "/users":
            raw = (params.get("ids") or "").strip()
            if not raw:
                return _response(400, {"error": "query parameter ids required"})
            ids = [i.strip() for i in raw.split(",") if i.strip()]
            if not ids:
                return _response(400, {"error": "no valid ids supplied"})
            if len(ids) > MAX_BATCH:
                return _response(400,
                                 {"error": f"at most {MAX_BATCH} ids per call"})
            if not all(i.isdigit() for i in ids):
                return _response(400, {"error": "all ids must be numeric"})
            return _response(200, {"results": _fetch_many(ids)})

        if path == "/sample":
            try:
                limit = int(params.get("limit", 20))
            except ValueError:
                return _response(400, {"error": "limit must be an integer"})
            if not 1 <= limit <= MAX_SAMPLE:
                return _response(400,
                                 {"error": f"limit must be 1 to {MAX_SAMPLE}"})
            return _response(200, {"results": _fetch_sample(limit)})

        return _response(404, {"error": f"no route for {path}"})

    except ClientError as exc:
        print("dynamodb error:", exc)
        return _response(502, {"error": "data store unavailable"})
    except Exception as exc:  # noqa: BLE001
        print("unhandled error:", exc)
        return _response(500, {"error": "internal error"})