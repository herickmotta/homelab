# Dummy values for tofu validate only. This example is never applied.
# Guest agent expects local:snippets/qemu-guest-agent.yaml on the node (module default).
# virtiofs defaults to [] so this guest receives no VirtioFS devices.
module "example" {
  source = "../../modules/proxmox-vm"

  node_name       = "pve1"
  vm_id           = 100
  name            = "example-vm"
  username        = "ubuntu"
  ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyOnlyNotRealAAAAAAAAAAAA example@invalid"]
  ipv4_address    = "192.0.2.10/24"
  gateway         = "192.0.2.1"
  dns_servers     = ["192.0.2.1"]
  cloud_image_id  = "local:import/ubuntu-24.04-server-cloudimg-amd64.qcow2"
  cores           = 1
  memory_mb       = 2048
  disk_gb         = 16
  datastore_id    = "local-lvm"
  bridge          = "vmbr0"
  tags            = ["example"]
}
