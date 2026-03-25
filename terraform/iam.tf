# ---------------------------------------------------------------------------
# IAM – Lambda execution role (least-privilege)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${var.project_name}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  description        = "Execution role for AB test analyzer Lambda"

  tags = local.common_tags
}

# VPC networking (required for Lambda-in-VPC)
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# CloudWatch Logs – scoped to the specific log group
data "aws_iam_policy_document" "lambda_logs" {
  statement {
    sid    = "AllowCloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "${aws_cloudwatch_log_group.lambda.arn}:*",
    ]
  }
}

resource "aws_iam_policy" "lambda_logs" {
  name        = "${var.project_name}-lambda-logs"
  description = "Allow Lambda to write to its CloudWatch log group"
  policy      = data.aws_iam_policy_document.lambda_logs.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_logs.arn
}

# Secrets Manager – read the single RDS credential secret
data "aws_iam_policy_document" "lambda_secrets" {
  statement {
    sid    = "AllowGetRdsSecret"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [aws_db_instance.postgres.master_user_secret[0].secret_arn]
  }

  statement {
    sid    = "AllowDecryptSecretsKms"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.rds.arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${data.aws_region.current.name}.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "lambda_secrets" {
  name        = "${var.project_name}-lambda-secrets"
  description = "Allow Lambda to read the RDS credential secret"
  policy      = data.aws_iam_policy_document.lambda_secrets.json
}

resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_secrets.arn
}

# KMS – decrypt Lambda environment variables
data "aws_iam_policy_document" "lambda_kms" {
  statement {
    sid    = "AllowDecryptLambdaEnv"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
    ]
    resources = [aws_kms_key.lambda.arn]
  }
}

resource "aws_iam_policy" "lambda_kms" {
  name        = "${var.project_name}-lambda-kms"
  description = "Allow Lambda to decrypt its environment variable KMS key"
  policy      = data.aws_iam_policy_document.lambda_kms.json
}

resource "aws_iam_role_policy_attachment" "lambda_kms" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_kms.arn
}

# ---------------------------------------------------------------------------
# IAM – RDS Enhanced Monitoring role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "rds_monitoring_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_monitoring" {
  name               = "${var.project_name}-rds-monitoring"
  assume_role_policy = data.aws_iam_policy_document.rds_monitoring_assume.json
  description        = "Enhanced Monitoring role for RDS"

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
