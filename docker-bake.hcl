group "default" {
  targets = ["core"]
}

group "solver-stack" {
  targets = ["core", "palace", "openems", "klayout", "josephson", "josim", "paraview"]
}

variable "SOURCE_REVISION" {
  default = "e09e901fc392079b6dc6c7e5160654ef4da50397"
}

target "common" {
  context = "."
  args = {
    SOURCE_REVISION = "${SOURCE_REVISION}"
  }
}

target "core" {
  inherits = ["common"]
  dockerfile = "docker/core.Dockerfile"
  tags = ["textlayout/core:local"]
}

target "palace" {
  inherits = ["common"]
  dockerfile = "docker/palace.Dockerfile"
  tags = ["textlayout/palace:local"]
}

target "openems" {
  inherits = ["common"]
  dockerfile = "docker/openems.Dockerfile"
  tags = ["textlayout/openems:local"]
}

target "klayout" {
  inherits = ["common"]
  dockerfile = "docker/klayout.Dockerfile"
  tags = ["textlayout/klayout:local"]
}

target "josephson" {
  inherits = ["common"]
  dockerfile = "docker/josephson.Dockerfile"
  tags = ["textlayout/josephson:local"]
}

target "josim" {
  inherits = ["common"]
  dockerfile = "docker/josim.Dockerfile"
  tags = ["textlayout/josim:local"]
}

target "paraview" {
  inherits = ["common"]
  dockerfile = "docker/paraview.Dockerfile"
  tags = ["textlayout/paraview:local"]
}
