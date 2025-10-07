variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_prefix" {
  description = "Prefix used for naming resources"
  type        = string
  default     = "async-image-uploader"
}

variable "env" {
  description = "Deployment environment (dev/stage/prod)"
  type        = string
  default     = "dev"
}
