terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 1. Batch Worker EC2 Instance (Oversized Compute)
resource "aws_instance" "analytics_batch_worker" {
  ami           = "ami-0c7217cdde317cfec"
  instance_type = "c5.4xlarge"

  tags = {
    Name        = "analytics-batch-worker-prod"
    Environment = "Production"
    Project     = "DataAnalytics"
  }
}

# 2. Internal Dashboard EC2 (Oversized Compute)
resource "aws_instance" "internal_dashboard" {
  ami           = "ami-0c7217cdde317cfec"
  instance_type = "m5.2xlarge"

  tags = {
    Name        = "internal-tooling-dashboard"
    Environment = "Internal"
  }
}

# 3. Unattached Migration EBS Volume (Unattached Storage Waste)
resource "aws_ebs_volume" "backup_migration_temp" {
  availability_zone = "us-east-1a"
  size              = 500
  type              = "gp3"

  tags = {
    Name    = "backup-volume-migration-temp"
    Purpose = "OldDatabaseMigration"
  }
}

# 4. Legacy Log EBS Volume (Unattached Storage Waste)
resource "aws_ebs_volume" "legacy_log_volume" {
  availability_zone = "us-east-1a"
  size              = 250
  type              = "gp2"

  tags = {
    Name        = "legacy-log-volume"
    Environment = "Legacy"
  }
}

# 5. Idle Serverless Lambda Function (Idle Serverless Waste)
resource "aws_lambda_function" "legacy_image_resizer" {
  function_name = "legacy-image-resizer"
  runtime       = "python3.9"
  handler       = "index.handler"
  role          = "arn:aws:iam::123456789012:role/lambda-role"
  filename      = "dummy_lambda.zip"
  memory_size   = 1024

  tags = {
    Deprecated = "true"
  }
}

# 6. Unassociated Elastic IP (Idle Networking Waste)
resource "aws_eip" "unassociated_ip" {
  domain = "vpc"

  tags = {
    Name = "unassociated-elastic-ip-1"
  }
}
