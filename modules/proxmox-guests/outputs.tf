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

output "directory_mapping_ids" {
  description = "Proxmox directory mapping identifiers managed by this module."
  value       = { for key, mapping in proxmox_hardware_mapping_dir.this : key => mapping.id }
}

output "virtiofs_mappings" {
  description = "VirtioFS mapping identifiers keyed by stable logical guest identity."
  value       = { for key, guest in module.guest : key => guest.virtiofs_mappings }
}
