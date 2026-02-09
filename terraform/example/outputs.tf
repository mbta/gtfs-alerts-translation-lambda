output "bucket_name" {
  value = aws_s3_bucket.test_bucket.id
}

output "url" {
  value = "https://${aws_s3_bucket.test_bucket.bucket_regional_domain_name}/${local.destination_path}"
}

output "lambda_arn" {
  value = module.gtfs_translator.lambda_function_arn
}
