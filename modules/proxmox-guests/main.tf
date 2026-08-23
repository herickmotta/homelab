resource "proxmox_hardware_mapping_dir" "this" {
  for_each = var.directory_mappings

  name    = each.key
  comment = each.value.comment
  map = [
    {
      node = var.node_name
      path = each.value.path
    }
  ]
}

resource "proxmox_hardware_mapping_pci" "this" {
  for_each = var.pci_mappings

  name    = each.key
  comment = each.value.comment
  map = [
    {
      node         = var.node_name
      path         = each.value.path
      id           = each.value.id
      iommu_group  = each.value.iommu_group
      subsystem_id = each.value.subsystem_id
    }
  ]
  mediated_devices = false
}

locals {
  guest_virtiofs_mappings = distinct(flatten([
    for guest in values(var.guests) : [
      for share in guest.virtiofs : share.mapping
    ]
  ]))

  guest_hostpci_mappings = distinct(flatten([
    for guest in values(var.guests) : [
      for device in guest.hostpci : device.mapping
    ]
  ]))
}

check "virtiofs_mappings_declared" {
  assert {
    condition = alltrue([
      for mapping in local.guest_virtiofs_mappings :
      contains(keys(var.directory_mappings), mapping)
    ])
    error_message = "Every guest VirtioFS mapping must exist in directory_mappings."
  }
}

check "hostpci_mappings_declared" {
  assert {
    condition = alltrue([
      for mapping in local.guest_hostpci_mappings :
      contains(keys(var.pci_mappings), mapping)
    ])
    error_message = "Every guest hostpci mapping must exist in pci_mappings."
  }
}

module "guest" {
  for_each = var.guests
  source   = "../proxmox-vm"

  node_name       = var.node_name
  vm_id           = each.value.vm_id
  name            = each.value.name
  username        = var.username
  ssh_public_keys = var.ssh_public_keys

  ipv4_address = "${each.value.ipv4}/${var.prefix_length}"
  gateway      = var.gateway
  dns_servers = (
    each.value.dns_servers != null
    ? each.value.dns_servers
    : var.dns_servers
  )

  cloud_image_id = var.cloud_image_id
  cores          = each.value.cores
  cpu_type       = each.value.cpu_type
  memory_mb      = each.value.memory_mb
  disk_gb        = each.value.disk_gb
  datastore_id = (
    each.value.datastore_id != null
    ? each.value.datastore_id
    : var.datastore_id
  )
  bridge = (
    each.value.bridge != null
    ? each.value.bridge
    : var.bridge
  )
  tags                = tolist(each.value.tags)
  stop_on_destroy     = each.value.stop_on_destroy
  vendor_data_file_id = var.vendor_data_file_id
  agent_timeout       = var.agent_timeout
  startup             = each.value.startup
  virtiofs            = each.value.virtiofs
  machine             = each.value.machine
  hostpci             = each.value.hostpci

  depends_on = [
    proxmox_hardware_mapping_dir.this,
    proxmox_hardware_mapping_pci.this,
  ]
}
