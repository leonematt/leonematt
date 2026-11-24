terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }
}

# Reads the API token from the CLOUDFLARE_API_TOKEN environment variable.
provider "cloudflare" {}

# CloudFront certificates must live in us-east-1, so everything goes there.
provider "aws" {
  region = "us-east-1"
}

locals {
  aliases = [var.domain, "www.${var.domain}"]
  bucket  = "${replace(var.domain, ".", "-")}-site"
}

# ---------- DNS zone (lives in Cloudflare) ----------
data "cloudflare_zone" "this" {
  name = var.domain
}

# ---------- S3 bucket (private; only CloudFront can read it) ----------
resource "aws_s3_bucket" "site" {
  bucket = local.bucket
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ---------- TLS certificate ----------
resource "aws_acm_certificate" "site" {
  domain_name               = var.domain
  subject_alternative_names = ["www.${var.domain}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# ACM validation CNAMEs, created in Cloudflare. Must be DNS-only (not proxied).
resource "cloudflare_record" "cert_validation" {
  for_each = {
    for o in aws_acm_certificate.site.domain_validation_options : o.domain_name => {
      name   = trimsuffix(o.resource_record_name, ".")
      type   = o.resource_record_type
      record = trimsuffix(o.resource_record_value, ".")
    }
  }
  zone_id         = data.cloudflare_zone.this.id
  name            = each.value.name
  type            = each.value.type
  content         = each.value.record
  ttl             = 60
  proxied         = false
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "site" {
  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for o in aws_acm_certificate.site.domain_validation_options : o.resource_record_name]
  depends_on              = [cloudflare_record.cert_validation]
}

# ---------- CloudFront ----------
resource "aws_cloudfront_origin_access_control" "site" {
  name                              = local.bucket
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Redirect www -> apex so there is one canonical URL.
resource "aws_cloudfront_function" "www_redirect" {
  name    = "${local.bucket}-www-redirect"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var req = event.request;
      var host = req.headers.host && req.headers.host.value;
      if (host && host.indexOf("www.") === 0) {
        return {
          statusCode: 301,
          statusDescription: "Moved Permanently",
          headers: { location: { value: "https://${var.domain}" + req.uri } }
        };
      }
      return req;
    }
  EOF
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  default_root_object = "index.html"
  aliases             = local.aliases
  price_class         = "PriceClass_All" # included in the CloudFront flat-rate plan

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-site"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id           = "s3-site"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.www_redirect.arn
    }
  }

  # Unknown paths (S3 returns 403 for missing keys with OAC) go to the homepage.
  custom_error_response {
    error_code         = 403
    response_code      = 404
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.site.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  # The flat-rate plan manages this distribution's WAF web ACL.
  lifecycle {
    ignore_changes = [web_acl_id]
  }
}

# Let only this distribution read the bucket.
resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontRead"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.site.arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.site.arn }
      }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.site]
}

# ---------- DNS records pointing at CloudFront ----------
# Cloudflare flattens the apex CNAME, so the bare domain works too.
# DNS-only (grey cloud): CloudFront is already the CDN and terminates TLS.
resource "cloudflare_record" "site" {
  for_each = toset(local.aliases)

  zone_id         = data.cloudflare_zone.this.id
  name            = each.value
  type            = "CNAME"
  content         = aws_cloudfront_distribution.site.domain_name
  ttl             = 300
  proxied         = false
  allow_overwrite = true
}
