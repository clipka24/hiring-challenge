output "sns_topic_arn" {
  description = "ARN of the SNS topic – publish AB test results here"
  value       = aws_sns_topic.ab_test_results.arn
}

output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = aws_lambda_function.ab_test_analyzer.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function"
  value       = aws_lambda_function.ab_test_analyzer.arn
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port)"
  value       = "${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}"
  sensitive   = true
}

output "rds_secret_arn" {
  description = "ARN of the Secrets Manager secret containing RDS credentials"
  value       = aws_db_instance.postgres.master_user_secret[0].secret_arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for the Lambda function"
  value       = aws_cloudwatch_log_group.lambda.name
}
