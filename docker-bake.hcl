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
    "adamtheturtle/vuforia-vws-mock:latest",
    "adamtheturtle/vuforia-vws-mock:${VERSION}",
  ]
}

target "vwq" {
  inherits = ["_base"]
  target   = "vwq"
  tags = [
    "adamtheturtle/vuforia-vwq-mock:latest",
    "adamtheturtle/vuforia-vwq-mock:${VERSION}",
  ]
}

target "target-manager" {
  inherits = ["_base"]
  target   = "target-manager"
  tags = [
    "adamtheturtle/vuforia-target-manager-mock:latest",
    "adamtheturtle/vuforia-target-manager-mock:${VERSION}",
  ]
}
