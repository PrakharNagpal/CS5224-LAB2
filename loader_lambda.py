

import json
import os
import urllib.parse

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "twitter_counts")
VERIFY_USERS = ["214328887", "107830991"]

_s3 = boto3.client("s3")
_table = boto3.resource("dynamodb").Table(TABLE_NAME)


def _iter_rows(bucket: str, prefix: str):
    """Yield every JSON record from every part file under the prefix."""
    paginator = _s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            body = _s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            for line in body.decode("utf-8").splitlines():
                line = line.strip()
                if line:
                    yield json.loads(line)


def lambda_handler(event, context):
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    trigger_key = urllib.parse.unquote_plus(record["object"]["key"])

    # the _SUCCESS marker sits alongside the part files
    prefix = trigger_key.rsplit("/", 1)[0] + "/"
    print(f"triggered by s3://{bucket}/{trigger_key}, loading prefix {prefix}")

    written = 0
    with _table.batch_writer(overwrite_by_pkeys=["user_id"]) as batch:
        for row in _iter_rows(bucket, prefix):
            batch.put_item(Item={
                "user_id": str(row["user_id"]),
                "followers": int(row["followers"]),
                "followees": int(row["followees"]),
            })
            written += 1
            if written % 10000 == 0:
                print(f"  written {written:,}")

    print(f"load complete: {written:,} items into {TABLE_NAME}")

    # verification, printed to CloudWatch for the report screenshot
    for uid in VERIFY_USERS:
        item = _table.get_item(Key={"user_id": uid}).get("Item")
        if item:
            print(f"{uid} has {int(item['followers'])} followers")
            print(f"{uid} has {int(item['followees'])} followees")
        else:
            print(f"{uid} not found after load")

    return {"statusCode": 200, "itemsWritten": written, "prefix": prefix}