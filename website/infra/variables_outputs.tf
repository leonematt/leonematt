variable "domain" {
  description = "Apex domain for the site (its zone must already exist in Cloudflare)"
  type        = string
  default     = "leonematt.com"
}

output "bucket" {
  value = aws_s3_bucket.site.bucket
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.site.domain_name
}
