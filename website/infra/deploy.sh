#!/usr/bin/env bash
# Upload the site and clear the CloudFront cache.
# Usage: infra/deploy.sh [site-folder]   (defaults to ../site)
set -euo pipefail

SITE_DIR="$(cd "${1:-$(dirname "$0")/../site}" && pwd)"
cd "$(dirname "$0")"

BUCKET=$(terraform output -raw bucket)
DIST=$(terraform output -raw distribution_id)

# HTML: always revalidate so edits show up right away.
aws s3 sync "$SITE_DIR" "s3://$BUCKET" --delete \
  --exclude "*" --include "*.html" \
  --cache-control "public, max-age=0, must-revalidate"

# Everything else (favicon, images): cache for a day.
aws s3 sync "$SITE_DIR" "s3://$BUCKET" --delete \
  --exclude "*.html" \
  --cache-control "public, max-age=86400"

aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" \
  --query 'Invalidation.Id' --output text

echo "Deployed to https://$(terraform output -raw cloudfront_domain) (and your domain)"
