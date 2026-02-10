# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

variables {
  channel = "latest/edge"
}

run "basic_deploy" {
  assert {
    condition     = module.github_runner_image_builder.app_name == "github-runner-image-builder"
    error_message = "Expected app_name output to match the configured app name."
  }

  assert {
    condition     = module.github_runner_image_builder.provides.github_runner_image_v0 == "image"
    error_message = "Expected provides.github_runner_image_v0 to be image."
  }

  assert {
    condition     = module.github_runner_image_builder.provides.cos_agent == "cos-agent"
    error_message = "Expected provides.cos_agent to be cos-agent."
  }
}
