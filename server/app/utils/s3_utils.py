
import os, boto3
S3_ENDPOINT=os.getenv("S3_ENDPOINT","http://localhost:9000")
S3_ACCESS_KEY=os.getenv("S3_ACCESS_KEY","minioadmin")
S3_SECRET_KEY=os.getenv("S3_SECRET_KEY","minioadmin")
S3_REGION=os.getenv("S3_REGION","us-east-1")
S3_BUCKET=os.getenv("S3_BUCKET","tus")
S3_USE_SSL=os.getenv("S3_USE_SSL","false").lower()=="true"

def s3_client():
    return boto3.client("s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_ACCESS_KEY,
                        aws_secret_access_key=S3_SECRET_KEY, region_name=S3_REGION, use_ssl=S3_USE_SSL)

def get_object_text(key: str, encoding="utf-8") -> str:
    c = s3_client(); resp = c.get_object(Bucket=S3_BUCKET, Key=key)
    return resp["Body"].read().decode(encoding, errors="ignore")
