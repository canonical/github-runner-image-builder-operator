import subprocess

subprocess.Popen(
    [
        "/home/ubuntu/.local/bin/github-runner-image-builder",
        "run",
        "cloudname",
        "imagename",
        "--base-image=jammy",
        "--keep-revision=2",
        "--callback-script=callback",
    ]
)
