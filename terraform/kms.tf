# ---------------------------------------------------------------------------
# KMS Keys – one per service for granular key policies
# ---------------------------------------------------------------------------

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}

# --- Lambda environment variables ---

resource "aws_kms_key" "lambda" {
  description             = "${var.project_name} Lambda environment variable encryption"
  deletion_window_in_days = 14
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_lambda.json

  tags = merge(local.common_tags, { Purpose = "lambda-env" })
}

resource "aws_kms_alias" "lambda" {
  name          = "alias/${var.project_name}/lambda"
  target_key_id = aws_kms_key.lambda.key_id
}

data "aws_iam_policy_document" "kms_lambda" {
  statement {
    sid     = "RootFullAccess"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
  statement {
    sid    = "LambdaDecrypt"
    effect = "Allow"
    actions = ["kms:Decrypt", "kms:GenerateDataKey"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.lambda_exec.arn]
    }
    resources = ["*"]
  }
}


# --- RDS ---

resource "aws_kms_key" "rds" {
  description             = "${var.project_name} RDS storage encryption"
  deletion_window_in_days = 14
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_rds.json

  tags = merge(local.common_tags, { Purpose = "rds" })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project_name}/rds"
  target_key_id = aws_kms_key.rds.key_id
}

data "aws_iam_policy_document" "kms_rds" {
  statement {
    sid     = "RootFullAccess"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
  statement {
    sid    = "RDSServiceAccess"
    effect = "Allow"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:CreateGrant",
      "kms:ListGrants",
      "kms:DescribeKey",
    ]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
    resources = ["*"]
  }
  statement {
    sid    = "LambdaDecryptSecret"
    effect = "Allow"
    actions = ["kms:Decrypt", "kms:GenerateDataKey"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.lambda_exec.arn]
    }
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${local.region}.amazonaws.com"]
    }
  }
}

# --- SNS ---

resource "aws_kms_key" "sns" {
  description             = "${var.project_name} SNS topic encryption"
  deletion_window_in_days = 14
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_sns.json

  tags = merge(local.common_tags, { Purpose = "sns" })
}

resource "aws_kms_alias" "sns" {
  name          = "alias/${var.project_name}/sns"
  target_key_id = aws_kms_key.sns.key_id
}

data "aws_iam_policy_document" "kms_sns" {
  statement {
    sid     = "RootFullAccess"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
  statement {
    sid    = "SNSServiceAccess"
    effect = "Allow"
    actions = [
      "kms:GenerateDataKey*",
      "kms:Decrypt",
    ]
    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }
    resources = ["*"]
  }
}

# --- CloudWatch Logs ---

resource "aws_kms_key" "cloudwatch" {
  description             = "${var.project_name} CloudWatch Logs encryption"
  deletion_window_in_days = 14
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_cloudwatch.json

  tags = merge(local.common_tags, { Purpose = "cloudwatch" })
}

resource "aws_kms_alias" "cloudwatch" {
  name          = "alias/${var.project_name}/cloudwatch"
  target_key_id = aws_kms_key.cloudwatch.key_id
}

data "aws_iam_policy_document" "kms_cloudwatch" {
  statement {
    sid     = "RootFullAccess"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
  statement {
    sid    = "CloudWatchLogsAccess"
    effect = "Allow"
    actions = [
      "kms:Encrypt*",
      "kms:Decrypt*",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
    ]
    principals {
      type        = "Service"
      identifiers = ["logs.${local.region}.amazonaws.com"]
    }
    resources = ["*"]
    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${local.region}:${local.account_id}:*"]
    }
  }
}
