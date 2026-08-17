output "vm_id" {
  description = "Proxmox VMID."
  value       = proxmox_virtual_environment_vm.this.vm_id
}

output "name" {
  description = "VM name / guest hostname."
  value       = proxmox_virtual_environment_vm.this.name
}

output "ipv4_address" {
  description = "Configured IPv4 CIDR (not discovered via guest agent)."
  value       = var.ipv4_address
}
