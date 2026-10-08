# S3-compatible remote state (Yandex Object Storage / VK Cloud S3) with per-env key.
# Bucket and credentials are injected at init time:  terraform init -backend-config=...
terraform {
  backend "s3" {
    key                         = "shop/prod/terraform.tfstate"
    region                      = "ru-central1"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
