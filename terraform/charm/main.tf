# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "github_runner_image_builder" {
  name  = var.app_name
  model = var.model

  charm {
    name     = "github-runner-image-builder"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  config      = var.config
  constraints = var.constraints
  units       = var.units
}
