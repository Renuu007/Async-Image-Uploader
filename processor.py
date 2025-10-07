import json
import os
import boto3
from urllib.parse import unquote_plus

s3 = boto3.client('s3')
ddb = boto3.client('dynamodb')
sns = boto3.client('sns')

BUCKET = os.environ.get('BUCKET_NAME')
DDB_TABLE = os.environ.get('DDB_TABLE')
SNS_TOPIC = os.environ.get('SNS_TOPIC')


def lambda_handler(event, context):
    # SQS event contains S3 key info (assuming client posts bucket/key details)
    # For demo, we expect messages of shape: {"s3_key": "path/to/object.jpg"}
    for record in event.get('Records', []):
        body = record.get('body')
        try:
            msg = json.loads(body)
        except Exception:
            msg = { 'body': body }

        s3_key = msg.get('s3_key')
        if not s3_key:
            # fallback - try to parse if event came from S3 directly
            # not implemented here
            continue

        s3_key = unquote_plus(s3_key)
        try:
            # simple "thumbnail" step: copy original to thumbnails/ prefix
            thumb_key = f"thumbnails/{s3_key.split('/')[-1]}"
            copy_source = {'Bucket': BUCKET, 'Key': s3_key}
            s3.copy_object(Bucket=BUCKET, CopySource=copy_source, Key=thumb_key)

            # write metadata to DynamoDB (simple record)
            ddb.put_item(
                TableName=DDB_TABLE,
                Item={
                    'id': {'S': s3_key},
                    'original_key': {'S': s3_key},
                    'thumbnail_key': {'S': thumb_key},
                }
            )

            # publish an SNS message about completion
            sns_msg = {
                'original': s3_key,
                'thumbnail': thumb_key
            }
            sns.publish(TopicArn=SNS_TOPIC, Message=json.dumps(sns_msg))

        except Exception as e:
            print('Error processing', s3_key, e)
            raise

    return { 'status': 'ok' }
