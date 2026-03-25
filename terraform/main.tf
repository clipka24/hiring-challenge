terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# Lambda deployment package
# ---------------------------------------------------------------------------

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/.build/lambda.zip"

  excludes = [
    "tests",
    "conftest.py",
    "__pycache__",
    "tests/__pycache__",
  ]
}

# ---------------------------------------------------------------------------
# SNS Topic
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "ab_test_results" {
  name              = "${var.project_name}-ab-test-results"
  kms_master_key_id = aws_kms_key.sns.id

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = aws_sns_topic.ab_test_results.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.ab_test_analyzer.arn
}

# Allow SNS to invoke the Lambda function
resource "aws_lambda_permission" "sns_invoke" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ab_test_analyzer.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.ab_test_results.arn
}

# ---------------------------------------------------------------------------
# Lambda Function
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "ab_test_analyzer" {
  function_name = "${var.project_name}-analyzer"
  description   = "Analyzes AB test interim results and writes winner to RDS"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "app.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 256

  role = aws_iam_role.lambda_exec.arn

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DB_SECRET_ARN = aws_db_instance.postgres.master_user_secret[0].secret_arn
    }
  }

  # Encrypt environment variables at rest
  kms_key_arn = aws_kms_key.lambda.arn

  layers = [aws_lambda_layer_version.psycopg2.arn]

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.ab_test_analyzer.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.cloudwatch.arn

  tags = local.common_tags
}

# psycopg2 layer (pre-built for Lambda / Amazon Linux 2023)
resource "aws_lambda_layer_version" "psycopg2" {
  layer_name          = "${var.project_name}-psycopg2"
  description         = "psycopg2-binary for Python 3.12"
  compatible_runtimes = ["python3.12"]

  # The actual layer ZIP must be provided; path configurable via variable.
  filename         = var.psycopg2_layer_zip_path
  source_code_hash = filebase64sha256(var.psycopg2_layer_zip_path)
}

# ---------------------------------------------------------------------------
# RDS PostgreSQL
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "rds" {
  name       = "${var.project_name}-rds-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = local.common_tags
}

resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-postgres"

  engine         = "postgres"
  engine_version = "18.3"
  instance_class = var.rds_instance_class

  db_name  = var.db_name
  username = var.db_master_username
  # Password managed via Secrets Manager rotation – set via manage_master_user_password
  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.rds.id

  # Storage
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  # Network
  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # Availability & backups
  multi_az               = var.rds_multi_az
  backup_retention_period = 7
  deletion_protection    = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.project_name}-final-snapshot"

  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval              = 60
  monitoring_role_arn              = aws_iam_role.rds_monitoring.arn

  tags = local.common_tags
}

