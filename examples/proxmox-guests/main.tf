# Dummy values for tofu validate only. This example is never applied.
module "example" {
  source = "../../modules/proxmox-guests"

  node_name       = "pve-example"
  cloud_image_id  = "local:import/ubuntu-24.04-server-cloudimg-amd64.qcow2"
  username        = "ubuntu"
  ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyOnlyNotRealAAAAAAAAAAAA example@invalid"]
  prefix_length   = 24
  gateway         = "192.0.2.1"
  dns_servers     = ["192.0.2.12"]
  datastore_id    = "local-lvm"
  bridge          = "vmbr0"

  guests = {
    network_plane = {
      name        = "net-example"
      vm_id       = 112
      ipv4        = "192.0.2.12"
      dns_servers = ["192.0.2.1"]
      cores       = 2
      memory_mb   = 4096
      disk_gb     = 16
      tags        = ["network"]
      startup = {
        order    = 1
        up_delay = 15
      }
    }

    application_runtime = {
      name      = "apps-example"
      vm_id     = 115
      ipv4      = "192.0.2.15"
      cores     = 4
      cpu_type  = "host"
      memory_mb = 8192
      disk_gb   = 64
      machine   = "q35"
      tags      = ["apps"]
      startup = {
        order = 3
      }
      virtiofs = [
        {
          mapping = "example-frigate"
        }
      ]
      hostpci = [
        {
          mapping = "example-igpu"
          pcie    = true
        }
      ]
    }

    nas_gateway = {
      name      = "nas-example"
      vm_id     = 114
      ipv4      = "192.0.2.14"
      cores     = 2
      memory_mb = 4096
      disk_gb   = 32
      tags      = ["nas"]
      startup = {
        order = 2
      }
      virtiofs = [
        {
          mapping    = "example-personal"
          expose_acl = true
        },
        {
          mapping    = "example-media"
          expose_acl = true
        }
      ]
    }

    observability = {
      name      = "observe-example"
      vm_id     = 116
      ipv4      = "192.0.2.16"
      cores     = 4
      memory_mb = 8192
      disk_gb   = 128
      tags      = ["observe"]
      startup = {
        order = 4
      }
    }
  }

  directory_mappings = {
    example-personal = {
      path    = "/srv/example/iron/personal"
      comment = "Fictional personal dataset"
    }
    example-media = {
      path    = "/srv/example/iron/media"
      comment = "Fictional media dataset"
    }
    example-frigate = {
      path    = "/srv/example/volatile/frigate"
      comment = "Fictional disposable camera footage"
    }
  }

  pci_mappings = {
    example-igpu = {
      id      = "8086:0000"
      path    = "0000:00:02.0"
      comment = "Fictional Intel iGPU mapping"
    }
  }
}
