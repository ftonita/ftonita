variable "name" {
  description = "Prefix for all network resources (e.g. shop-prod)."
  type        = string
}

variable "cidr" {
  description = "Subnet CIDR."
  type        = string

  validation {
    condition     = can(cidrhost(var.cidr, 0))
    error_message = "cidr must be a valid IPv4 CIDR block."
  }
}

variable "external_network_id" {
  description = "ID of the external (public) network used as router gateway."
  type        = string
}

variable "dns_nameservers" {
  description = "DNS servers handed out by DHCP."
  type        = list(string)
  default     = ["77.88.8.8", "1.1.1.1"]
}
