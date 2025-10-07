# Async Image Uploader & Thumbnail Processor — Terraform starter

## What this creates
- S3 bucket (private) for images
- CloudFront distribution to serve images
- SQS queue to submit processing jobs
- Lambda worker triggered by SQS
- DynamoDB table to store metadata
- SNS topic for completion events

## How it works
1. Upload an image to the S3 bucket (e.g., `uploads/image.jpg`).
2. Send a JSON message to the SQS queue with `{ "s3_key": "uploads/image.jpg" }`.
3. Lambda receives the SQS message, copies the original to `thumbnails/` (simulated thumbnail), writes metadata to DynamoDB, and publishes a message to SNS.
4. Images are served via CloudFront (distribution domain in outputs).

## Usage
1. Ensure you have `terraform` installed.
2. `terraform init`
3. `terraform apply` (accept plan)

## Notes / Next steps
- This starter **does not** include real image resizing. To add real thumbnailing, bundle Pillow into the Lambda package (use a Lambda layer or build a deployment package with dependencies).
- Consider using CloudFront Origin Access Control (OAC) or signed URLs for tighter security and private access patterns.
- Add monitoring (CloudWatch alarms) and dead-letter queue (DLQ) for SQS.
