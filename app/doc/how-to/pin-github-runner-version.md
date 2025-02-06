# How to pin GitHub runner version

The GitHub runner API for fetching the [GitHub runner applications download URL](https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#list-runner-applications-for-an-organization) may provide different versions
of the GitHub actions runner from the [latest release](https://github.com/actions/runner/releases).

In order to pin a specific GitHub [actions runner](https://github.com/actions/runner) version, add
the `--runner-version` argument with the desired version during the build.

```
github-runner-image-builder <cloud-name> <image-name> --runner-version=<runner-version>
```

Find out what versions of runner versions are available 
[here](https://github.com/actions/runner/releases).
