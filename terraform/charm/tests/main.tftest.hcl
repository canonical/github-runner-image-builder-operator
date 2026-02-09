# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

variables {
  channel  = "latest/edge"
  revision = 1
}

run "basic_deploy" {
  assert {
    condition     = outputs.app_name == "test-github-runner-image-builder"
    error_message = "Expected app_name output to match the configured app name."
  }

  assert {
    condition     = outputs.provides.github_runner_image_v0 == "image"
    error_message = "Expected provides.github_runner_image_v0 to be image."
  }

  assert {
    condition     = outputs.provides.cos_agent == "cos-agent"
    error_message = "Expected provides.cos_agent to be cos-agent."
  }

  assert {
    condition     = length(outputs.requires) == 0
    error_message = "Expected requires to be empty."
  }
}
