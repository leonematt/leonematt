# website

Personal site for [leonematt.com](https://leonematt.com), hosted on AWS.

```
site/    index.html, favicon.svg, images/profile.jpg  (the page)
infra/   Terraform + deploy.sh    (S3, CloudFront, ACM, Cloudflare DNS)
```

## Architecture

S3 (private) → CloudFront (HTTPS, HTTP/3, security headers, www → apex redirect).
DNS stays in **Cloudflare**; Terraform adds only the site and certificate records,
so existing email records (MX, SPF, DKIM, DMARC) are left alone.
Expected cost: well under $1/month for a low-traffic site.

## 0. Before you start

1. **Cloudflare API token:** Cloudflare dashboard → My Profile → API Tokens →
   Create Token → "Edit zone DNS" template → limit it to `leonematt.com`.
2. **Delete any existing `@` and `www` records** in Cloudflare that point to the old
   site (Vercel etc.). Terraform will create new ones. Leave MX/TXT records alone.

## 1. Create the infrastructure

```bash
cd infra
aws configure                         # or: aws sso login
export CLOUDFLARE_API_TOKEN=...       # from step 0
terraform init -backend-config=backend.hcl
terraform apply                       # ~5–15 min, mostly CloudFront
```

## 2. Deploy the site

```bash
infra/deploy.sh        # uploads site/ and clears the CloudFront cache
```

Rerun it any time you change the page.

## 3. Check

- https://leonematt.com loads with a valid certificate
- https://www.leonematt.com redirects to https://leonematt.com
- In Cloudflare, the `@` and `www` records show a **grey cloud** (DNS only)

## Terraform state

Stored in S3 (versioned, encrypted, S3-native locking) under the key
`leonematt-website/terraform.tfstate`. The bucket name is kept out of git in
`infra/backend.hcl`:

```bash
cd infra
cp backend.hcl.example backend.hcl      # set bucket = "<your state bucket>"
terraform init -backend-config=backend.hcl
```

## Profile photo

Put your photo at `site/images/profile.jpg` (a square crop works best).
Until it exists, the page shows "ML" initials instead.
