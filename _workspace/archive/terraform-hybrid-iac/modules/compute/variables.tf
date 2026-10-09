variable "name" {
  description = "Prefix for instance and security group names."
  type        = string
}

variable "network_id" {
  type = string
}

variable "image_name" {
  type    = string
  default = "Ubuntu-22.04-Standard"
}

variable "key_pair" {
  description = "Name of an existing SSH key pair."
  type        = string
}

variable "instances" {
  description = "Map of instance key => { flavor, role }."
  type = map(object({
    flavor = string
    role   = string
  }))
}

variable "ingress_rules" {
  description = "Allowed inbound traffic. Default is deny."
  type = list(object({
    protocol = string
    port     = number
    cidr     = string
  }))
  default = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
