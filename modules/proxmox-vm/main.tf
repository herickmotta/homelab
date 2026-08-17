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
  scsi_hardware   = "virtio-scsi-pci"
  boot_order      = ["scsi0"]

  agent {
    # Must stay false at create time: Ubuntu cloud images do not ship qemu-guest-agent,
    # and enabled=true makes the provider wait for it. The virtio port is therefore
    # absent; Ansible installs the package and starts the service only if the port exists.
    enabled = false
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
}
