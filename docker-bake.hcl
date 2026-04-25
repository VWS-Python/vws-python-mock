variable "VERSION" {
  default = "latest"
}

group "default" {
  targets = ["vws", "vwq", "target-manager"]
}

target "_base" {
  dockerfile = "src/mock_vws/_flask_server/Dockerfile"
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

target "vwq" {
  inherits = ["_base"]
  target   = "vwq"
  tags = [
    "ghcr.io/vws-python/vuforia-vwq-mock:latest",
    "ghcr.io/vws-python/vuforia-vwq-mock:${VERSION}",
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
