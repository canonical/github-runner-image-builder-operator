# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

locals {
  image_builder_app_name = "github-runner-image-builder"
  juju_model_name        = "test-deploy-image-builder"
}

terraform {
  required_version = ">= 1.6.6"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "~> 1.2.0"
    }
  }
}

provider "juju" {}

variable "channel" {
  type    = string
  default = "latest/edge"
}

data "juju_model" "image_builder" {
  name  = local.juju_model_name
  owner = "admin"
}

module "github_runner_image_builder" {
  source = "./.."

  app_name   = local.image_builder_app_name
  channel    = var.channel
  model_uuid = data.juju_model.image_builder.uuid
}

output "app_name" {
  value = module.github_runner_image_builder.app_name
}

output "provides" {
  value = module.github_runner_image_builder.provides
}

output "requires" {
  value = module.github_runner_image_builder.requires
}
