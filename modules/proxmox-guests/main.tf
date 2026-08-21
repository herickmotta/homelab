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
}
