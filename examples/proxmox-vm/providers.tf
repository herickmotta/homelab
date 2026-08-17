# Dummy values for tofu validate only. This example is never applied.
provider "proxmox" {
  endpoint  = "https://pve1.example.test:8006/"
  api_token = "terraform@pve!example=00000000-0000-0000-0000-000000000000"
  insecure  = true
}
