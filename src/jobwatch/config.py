import json
import os


def load_json(name):
    bucket = os.environ.get("CONFIG_BUCKET")
    if bucket:
        import boto3
        obj = boto3.client("s3").get_object(Bucket=bucket, Key=f"config/{name}")
        return json.loads(obj["Body"].read())
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.environ.get("JOBWATCH_CONFIG_DIR", os.path.join(here, "..", "..", "config"))
    with open(os.path.join(base, name), encoding="utf-8") as f:
        return json.load(f)


def get_secret(name):
    """Local: env var JOBWATCH_<NAME>. AWS: SSM Parameter Store under SSM_PREFIX."""
    env = os.environ.get("JOBWATCH_" + name.upper())
    if env:
        return env
    import boto3
    prefix = os.environ.get("SSM_PREFIX", "/jobwatch")
    resp = boto3.client("ssm").get_parameter(Name=f"{prefix}/{name}", WithDecryption=True)
    return resp["Parameter"]["Value"]
