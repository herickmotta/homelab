variable "node_name" {
  type        = string
  description = "Proxmox node that will host the VM."
}

variable "vm_id" {
  type        = number
  description = "Numeric VMID on the Proxmox cluster."
}

variable "name" {
  type        = string
  description = "Guest hostname and Proxmox VM name. Must be a valid DNS label."
}

variable "username" {
  type        = string
  description = "cloud-init user created on first boot."
  default     = "ubuntu"
}

variable "ssh_public_keys" {
  type        = list(string)
  description = "OpenSSH public keys installed for username."
}

variable "ipv4_address" {
  type        = string
  description = "Guest IPv4 address in CIDR notation (for example 192.0.2.10/24)."
}

variable "gateway" {
  type        = string
  description = "IPv4 default gateway."
}

variable "dns_servers" {
  type        = list(string)
  description = "DNS resolvers passed to cloud-init. Empty keeps image defaults."
  default     = []
}

variable "cloud_image_id" {
  type        = string
  description = "Proxmox file id of an imported cloud image (download_file resource id)."
}

variable "cores" {
  type        = number
  description = "vCPU count."
  default     = 1
}

variable "cpu_type" {
  type        = string
  description = "QEMU CPU type. x86-64-v2-AES is the bpg/proxmox default recommendation."
  default     = "x86-64-v2-AES"
}

variable "memory_mb" {
  type        = number
  description = "Dedicated RAM in MiB."
  default     = 2048
}

variable "disk_gb" {
  type        = number
  description = "Boot disk size in GiB after import."
  default     = 16
}

variable "datastore_id" {
  type        = string
  description = "Datastore for the VM disk and cloud-init drive. local-lvm is the Proxmox default."
  default     = "local-lvm"
}

variable "bridge" {
  type        = string
  description = "Linux bridge for the virtio NIC. vmbr0 is the Proxmox default."
  default     = "vmbr0"
}

variable "tags" {
  type        = list(string)
  description = "Proxmox tags (sorted by the API)."
  default     = []
}

variable "stop_on_destroy" {
  type        = bool
  description = "Stop instead of ACPI shutdown on destroy. Keep true as a safety net if the guest agent is down."
  default     = true
}

variable "vendor_data_file_id" {
  type        = string
  description = <<-EOT
    Proxmox snippet id with cloud-init vendor-data that installs qemu-guest-agent
    (default local:snippets/qemu-guest-agent.yaml). Copy modules/proxmox-vm/cloud-init/vendor-data.yaml
    onto the node first. Empty string skips vendor-data; new guests will then hang until qemu-ga exists.
  EOT
  default     = "local:snippets/qemu-guest-agent.yaml"
}

variable "agent_timeout" {
  type        = string
  description = "How long the provider waits for qemu-guest-agent after start (first-boot apt needs this)."
  default     = "15m"
}
