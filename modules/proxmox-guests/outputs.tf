output "vm_ids" {
  description = "VM IDs keyed by stable logical guest identity."
  value       = { for key, guest in module.guest : key => guest.vm_id }
}

output "names" {
  description = "Guest names keyed by stable logical guest identity."
  value       = { for key, guest in module.guest : key => guest.name }
}

output "ipv4_addresses" {
  description = "Configured IPv4 CIDRs keyed by stable logical guest identity."
  value       = { for key, guest in module.guest : key => guest.ipv4_address }
}
