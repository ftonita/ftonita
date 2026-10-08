terraform {
  required_version = ">= 1.5"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 2.1"
    }
  }
}

resource "openstack_networking_secgroup_v2" "this" {
  name        = "${var.name}-sg"
  description = "Managed by Terraform: ${var.name}"
}

resource "openstack_networking_secgroup_rule_v2" "ingress" {
  for_each = { for r in var.ingress_rules : "${r.protocol}-${r.port}" => r }

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = each.value.protocol
  port_range_min    = each.value.port
  port_range_max    = each.value.port
  remote_ip_prefix  = each.value.cidr
  security_group_id = openstack_networking_secgroup_v2.this.id
}

resource "openstack_compute_instance_v2" "this" {
  for_each = var.instances

  name            = "${var.name}-${each.key}"
  image_name      = var.image_name
  flavor_name     = each.value.flavor
  key_pair        = var.key_pair
  security_groups = [openstack_networking_secgroup_v2.this.name]

  network {
    uuid = var.network_id
  }

  metadata = merge(var.tags, { role = each.value.role })
}
