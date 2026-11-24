# Relation endpoints

This page describes the relation endpoints supported by the GitHub Runner Image Builder charm.

## `image` (provides)

* **Interface**: `github_runner_image_v0`
* **Supported charms**: [GitHub Runner operator](https://charmhub.io/github-runner)

Provides built VM images to charms that manage GitHub self-hosted runners. When a relation is
joined, the image builder shares the latest built image ID and its associated tags (for example, `x64`,
`jammy`) via the relation data.

The relation data published by this charm includes:

| Key | Type | Description |
|-----|------|-------------|
| `id` | string | ID of the latest built image. |
| `tags` | string | Comma-separated tags describing the image (for example, `x64,jammy`). |
| `images` | JSON string | List of image objects, each with `id` and `tags` fields. |

Example integrate command:

```bash
juju integrate github-runner-image-builder:image github-runner:image
```

## `cos-agent` (provides)

* **Interface**: `cos_agent`
* **Supported charms**: [Grafana Agent operator](https://charmhub.io/grafana-agent)

Integrates with the [Canonical Observability Stack (COS)](https://charmhub.io/topics/canonical-observability-stack)
via the Grafana Agent operator. Enables collection and forwarding of metrics, logs, and traces from
the image builder to your COS deployment.

Example integrate command:

```bash
juju integrate github-runner-image-builder:cos-agent grafana-agent:cos-agent
```
