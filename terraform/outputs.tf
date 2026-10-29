output "lambda_name" {
  value = aws_lambda_function.scanner.function_name
}

output "config_bucket" {
  value = aws_s3_bucket.config.id
}

output "state_table" {
  value = aws_dynamodb_table.state.name
}
