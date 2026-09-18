variable "aws_region" {
  type        = string
  description = "Target deployment AWS region"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "production"
}
