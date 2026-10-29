variable "VERSION" {
  default = "latest"
}

group "default" {
  targets = ["vws", "target-manager"]
}

target "_base" {
  dockerfile = "server/Dockerfile"
  platforms  = ["linux/amd64", "linux/arm64"]
}

target "vws" {
  inherits = ["_base"]
  target   = "vws"
  tags = [
    "ghcr.io/vws-python/vuforia-vws-mock:latest",
    "ghcr.io/vws-python/vuforia-vws-mock:${VERSION}",
  ]
}


target "target-manager" {
  inherits = ["_base"]
  target   = "target-manager"
  tags = [
    "ghcr.io/vws-python/vuforia-target-manager-mock:latest",
    "ghcr.io/vws-python/vuforia-target-manager-mock:${VERSION}",
  ]
}
