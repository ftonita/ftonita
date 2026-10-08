output "private_ips" {
  value = { for k, i in openstack_compute_instance_v2.this : k => i.access_ip_v4 }
}
