# Remote state in S3. The bucket name lives in infra/backend.hcl (gitignored)
# so the AWS account ID isn't published. First time:
#   cp backend.hcl.example backend.hcl   # fill in the bucket name
#   terraform init -backend-config=backend.hcl
terraform {
  backend "s3" {
    key          = "leonematt-website/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
