# ---------------------------------------------------------------------------
# Security Groups
# ---------------------------------------------------------------------------

# Lambda security group – egress only to RDS and AWS service endpoints
resource "aws_security_group" "lambda" {
  name        = "${var.project_name}-lambda-sg"
  description = "Security group for AB test analyzer Lambda function"
  vpc_id      = var.vpc_id

  # Outbound to RDS
  egress {
    description     = "PostgreSQL to RDS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.rds.id]
  }

  # Outbound HTTPS to AWS service endpoints (Secrets Manager, etc.)
  egress {
    description = "HTTPS to AWS service endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Restricted further via VPC endpoint policies in production
  }

  tags = merge(local.common_tags, { Name = "${var.project_name}-lambda-sg" })
}

# RDS security group – accepts traffic only from the Lambda SG
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group for AB test analyzer RDS instance"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from Lambda"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  egress {
    description = "No outbound traffic allowed"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
  }

  tags = merge(local.common_tags, { Name = "${var.project_name}-rds-sg" })
}
