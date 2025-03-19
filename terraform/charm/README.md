# GitHub runner image builder Terraform module

This folder contains a base [Terraform][Terraform] module for the GitHub runner image builder charm.

The module uses the [Terraform Juju provider][Terraform Juju provider] to model the charm
deployment onto any Kubernetes environment managed by [Juju][Juju].

## Module structure

- **main.tf** - Defines the Juju application to be deployed.
- **variables.tf** - Allows customization of the deployment. Also models the charm configuration, 
  except for exposing the deployment options (Juju model name, channel or application name).
- **output.tf** - Integrates the module with other Terraform modules, primarily
  by defining potential integration endpoints (charm integrations), but also by exposing
  the Juju application name.
- **versions.tf** - Defines the Terraform provider version.

## Using github-runner-image-builder base module in higher level modules

If you want to use `github-runner-image-builder` base module as part of your Terraform module, import it
like shown below:

```text
data "juju_model" "my_model" {
  name = var.model
}

module "ghib" {
  source = "git::https://github.com/canonical/github-runner-image-builder//terraform"

  model = juju_model.my_model.name
  # (Customize configuration variables here if needed)
}
```

Create integrations, for instance:

```text
resource "juju_integration" "ghib-nrf" {
  model = juju_model.my_model.name
  application {
    name     = module.ghib.app_name
    endpoint = module.ghib.provides.github_runner_image_v0
  }
  application {
    name     = "github-runner"
    endpoint = "image"
  }
}
```

The complete list of available integrations can be found [in the Integrations tab][github-runner-image-builder-integrations].

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[github-runner-image-builder-integrations]: https://charmhub.io/github-runner-image-builder/integrations
