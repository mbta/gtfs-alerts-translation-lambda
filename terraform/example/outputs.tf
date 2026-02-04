output "bucket_name" {
  value = aws_s3_bucket.test_bucket.id
}

output "lambda_arn" {
  value = module.gtfs_translator.lambda_function_arn
}
