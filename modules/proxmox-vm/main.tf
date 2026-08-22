resource "proxmox_virtual_environment_vm" "this" {
  name        = var.name
  vm_id       = var.vm_id
  node_name   = var.node_name
  description = "Managed by OpenTofu."
  tags        = var.tags

  stop_on_destroy = var.stop_on_destroy
  started         = true
  on_boot         = true
  bios            = "seabios"
  scsi_hardware   = "virtio-scsi-single"
  boot_order      = ["scsi0"]

  agent {
    # Channel on from first boot. Ubuntu cloud images do not ship qemu-guest-agent;
    # vendor-data (see vendor_data_file_id) installs it so the provider wait succeeds.
    enabled = true
    timeout = var.agent_timeout
  }

  cpu {
    cores = var.cores
    type  = var.cpu_type
  }

  memory {
    dedicated = var.memory_mb
  }

  disk {
    datastore_id = var.datastore_id
    interface    = "scsi0"
    import_from  = var.cloud_image_id
    size         = var.disk_gb
    discard      = "on"
    iothread     = true
    file_format  = "raw"
  }

  network_device {
    bridge = var.bridge
    model  = "virtio"
  }

  initialization {
    datastore_id = var.datastore_id
    interface    = "ide2"

    dynamic "dns" {
      for_each = length(var.dns_servers) > 0 ? [1] : []
      content {
        servers = var.dns_servers
      }
    }

    ip_config {
      ipv4 {
        address = var.ipv4_address
        gateway = var.gateway
      }
    }

    user_account {
      username = var.username
      keys     = [for k in var.ssh_public_keys : trimspace(k)]
    }

    # Snippet must already exist on the node. Empty string omits vendor-data.
    vendor_data_file_id = var.vendor_data_file_id != "" ? var.vendor_data_file_id : null
  }

  operating_system {
    type = "l26"
  }

  serial_device {
    device = "socket"
  }

  vga {
    type = "serial0"
  }

  dynamic "startup" {
    for_each = var.startup == null ? [] : [var.startup]
    content {
      order      = startup.value.order
      up_delay   = startup.value.up_delay
      down_delay = startup.value.down_delay
    }
  }

  dynamic "virtiofs" {
    for_each = var.virtiofs
    content {
      mapping      = virtiofs.value.mapping
      cache        = virtiofs.value.cache
      direct_io    = virtiofs.value.direct_io
      expose_acl   = virtiofs.value.expose_acl
      expose_xattr = virtiofs.value.expose_xattr
    }
  }

  # Adding vendor_data_file_id later ForceNew-replaces the VM. Keep it for
  # create (new guests install qemu-ga on first boot) but never replace an
  # existing disk to attach it.
  lifecycle {
    ignore_changes = [
      initialization[0].vendor_data_file_id,
    ]
  }
}
