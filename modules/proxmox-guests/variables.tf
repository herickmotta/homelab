variable "node_name" {
  type        = string
  description = "Proxmox node that hosts the guests."
}

variable "cloud_image_id" {
  type        = string
  description = "Proxmox file id of the cloud image imported by the calling root."
}

variable "username" {
  type        = string
  description = "Default cloud-init user for all guests."
  default     = "ubuntu"
}

variable "ssh_public_keys" {
  type        = list(string)
  description = "OpenSSH public keys installed for the cloud-init user."
}

variable "prefix_length" {
  type        = number
  description = "IPv4 prefix length appended to each guest address."

  validation {
    condition     = var.prefix_length >= 1 && var.prefix_length <= 32
    error_message = "prefix_length must be between 1 and 32."
  }
}

variable "gateway" {
  type        = string
  description = "Default IPv4 gateway for all guests."
}

variable "dns_servers" {
  type        = list(string)
  description = "Default DNS resolvers. A guest may override this list."
  default     = []
}

variable "datastore_id" {
  type        = string
  description = "Default Proxmox datastore for guest OS and cloud-init disks."
  default     = "local-lvm"
}

variable "bridge" {
  type        = string
  description = "Default Proxmox Linux bridge for guest interfaces."
  default     = "vmbr0"
}

variable "vendor_data_file_id" {
  type        = string
  description = "Cloud-init vendor-data snippet passed to each guest."
  default     = "local:snippets/qemu-guest-agent.yaml"
}

variable "agent_timeout" {
  type        = string
  description = "How long the provider waits for qemu-guest-agent."
  default     = "15m"
}

variable "directory_mappings" {
  description = <<-EOT
    Proxmox directory mappings keyed by stable mapping identifier. Empty by
    default. Paths are POSIX directories on node_name; the calling site must
    create those directories before apply. Mapping names are attached to guests
    through virtiofs[].mapping.
  EOT
  type = map(object({
    path    = string
    comment = optional(string)
  }))
  default = {}

  validation {
    condition = alltrue([
      for key in keys(var.directory_mappings) : can(regex("^[A-Za-z][A-Za-z0-9._-]*$", key))
    ])
    error_message = "Directory mapping keys must start with a letter."
  }

  validation {
    condition = alltrue([
      for mapping in values(var.directory_mappings) : startswith(mapping.path, "/")
    ])
    error_message = "Directory mapping paths must be absolute POSIX paths."
  }
}

variable "guests" {
  description = <<-EOT
    Guests keyed by stable logical identity. A key change is a resource address
    change and requires an explicit state migration. virtiofs defaults to no
    devices. startup null leaves Proxmox start order unmanaged.
  EOT

  type = map(object({
    name            = string
    vm_id           = number
    ipv4            = string
    dns_servers     = optional(list(string))
    cores           = optional(number, 1)
    cpu_type        = optional(string, "x86-64-v2-AES")
    memory_mb       = optional(number, 2048)
    disk_gb         = optional(number, 16)
    datastore_id    = optional(string)
    bridge          = optional(string)
    tags            = optional(set(string), [])
    stop_on_destroy = optional(bool, true)
    startup = optional(object({
      order      = number
      up_delay   = optional(number)
      down_delay = optional(number)
    }))
    virtiofs = optional(list(object({
      mapping      = string
      cache        = optional(string, "auto")
      direct_io    = optional(bool, false)
      expose_acl   = optional(bool, false)
      expose_xattr = optional(bool, false)
    })), [])
  }))

  validation {
    condition = length(distinct([
      for guest in values(var.guests) : guest.vm_id
    ])) == length(var.guests)
    error_message = "Every guest must have a unique vm_id."
  }

  validation {
    condition = length(distinct([
      for guest in values(var.guests) : guest.ipv4
    ])) == length(var.guests)
    error_message = "Every guest must have a unique ipv4 address."
  }

  validation {
    condition = alltrue([
      for key in keys(var.guests) : can(regex("^[a-z][a-z0-9_]*$", key))
    ])
    error_message = "Guest keys must be stable lowercase logical identifiers."
  }

  validation {
    condition = alltrue([
      for guest in values(var.guests) :
      length(distinct([for share in guest.virtiofs : share.mapping])) == length(guest.virtiofs)
    ])
    error_message = "Each guest must use unique VirtioFS mapping identifiers."
  }
}
