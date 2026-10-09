terraform {
  required_version = ">= 1.5"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 2.1"
    }
  }
}

# Credentials come from OS_* environment variables (set as masked GitLab CI variables).
provider "openstack" {}

locals {
  name = "shop-prod"
  tags = { env = "prod", managed_by = "terraform" }
}

module "network" {
  source              = "../../modules/network"
  name                = local.name
  cidr                = "10.30.0.0/24"
  external_network_id = var.external_network_id
}

module "compute" {
  source     = "../../modules/compute"
  name       = local.name
  network_id = module.network.network_id
  key_pair   = var.key_pair
  tags       = local.tags

  instances = {
    app-1 = { flavor = "Standard-4-8-50", role = "app" }
    app-2 = { flavor = "Standard-4-8-50", role = "app" }
  }

  ingress_rules = [
    { protocol = "tcp", port = 22, cidr = var.admin_cidr },
    { protocol = "tcp", port = 443, cidr = "0.0.0.0/0" },
  ]
}

variable "external_network_id" {
  type = string
}

variable "key_pair" {
  type = string
}

variable "admin_cidr" {
  description = "Bastion / VPN range allowed to SSH."
  type        = string
  default     = "10.0.0.0/16"
}

output "private_ips" {
  value = module.compute.private_ips
}
