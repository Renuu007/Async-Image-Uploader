terraform {
  required_version = ">= 1.1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "${var.project_prefix}-${var.env}"
}

# random id to avoid name collisions for global resources
resource "random_id" "suffix" {
  byte_length = 4
}

# -----------------------------
# S3 bucket (images)
# -----------------------------
resource "aws_s3_bucket" "images" {
  bucket = "${local.name_prefix}-images-${random_id.suffix.hex}"
  acl    = "private"

  force_destroy = true

  tags = {
    Name = "${local.name_prefix}-images"
    Env  = var.env
  }
}

resource "aws_s3_bucket_public_access_block" "images_block" {
  bucket = aws_s3_bucket.images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Origin Access Identity (OAI) to secure S3 origin
resource "aws_cloudfront_origin_access_identity" "oai" {
  comment = "OAI for ${local.name_prefix} images"
}

# Allow CloudFront OAI to read objects
resource "aws_s3_bucket_policy" "images_policy" {
  bucket = aws_s3_bucket.images.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "AllowCloudFrontServicePrincipalReadOnly"
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.oai.iam_arn
        }
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = [
          "${aws_s3_bucket.images.arn}/*"
        ]
      }
    ]
  })
}

# -----------------------------
# SQS queue and SNS topic
# -----------------------------
resource "aws_sqs_queue" "image_queue" {
  name                       = "${local.name_prefix}-image-queue"
  visibility_timeout_seconds = 120
  message_retention_seconds  = 86400
}

resource "aws_sns_topic" "thumbnail_topic" {
  name = "${local.name_prefix}-thumbnail-topic"
}

# -----------------------------
# DynamoDB table for metadata
# -----------------------------
resource "aws_dynamodb_table" "metadata" {
  name         = "${local.name_prefix}-metadata"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Env = var.env
  }
}

# -----------------------------
# IAM role & policy for Lambda
# -----------------------------
resource "aws_iam_role" "lambda_role" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        Resource = [
          aws_s3_bucket.images.arn,
          "${aws_s3_bucket.images.arn}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ],
        Resource = aws_dynamodb_table.metadata.arn
      },
      {
        Effect = "Allow",
        Action = [
          "sns:Publish"
        ],
        Resource = aws_sns_topic.thumbnail_topic.arn
      }
    ]
  })
}

# -----------------------------
# Lambda function (worker)
# -----------------------------
# Write the lambda source code to a local file (processor.py) using the local_file resource.
resource "local_file" "lambda_source" {
  content  = file("${path.module}/lambda/processor.py")
  filename = "${path.module}/lambda/processor.py" # ensures file exists when archiving
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = ["${path.module}/lambda/processor.py"]
  output_path = "${path.module}/lambda/processor.zip"
}

resource "aws_lambda_function" "processor" {
  function_name = "${local.name_prefix}-processor"
  filename      = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler       = "processor.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 120

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.images.bucket
      DDB_TABLE   = aws_dynamodb_table.metadata.name
      SNS_TOPIC   = aws_sns_topic.thumbnail_topic.arn
    }
  }
}

# Event mapping: SQS -> Lambda
resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.image_queue.arn
  function_name    = aws_lambda_function.processor.arn
  enabled          = true
  batch_size       = 5
}

# Allow SNS to invoke lambda if you want (optional): not needed here, but keep for reference
resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.processor.function_name
  principal     = "sns.amazonaws.com"
  #source_arn    = aws_sns_topic.thumbnail_topic.arn
}

# -----------------------------
# CloudFront distribution to serve images
# -----------------------------
resource "aws_cloudfront_distribution" "cdn" {
  enabled = true

  origin {
    domain_name = aws_s3_bucket.images.bucket_regional_domain_name
    origin_id   = "s3-images-origin"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-images-origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Env = var.env
  }
}

# -----------------------------
# Outputs
# -----------------------------
output "s3_bucket_name" {
  value = aws_s3_bucket.images.bucket
}

output "sqs_queue_url" {
  value = aws_sqs_queue.image_queue.id
}

output "lambda_name" {
  value = aws_lambda_function.processor.function_name
}

output "dynamodb_table" {
  value = aws_dynamodb_table.metadata.name
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.cdn.domain_name
}
