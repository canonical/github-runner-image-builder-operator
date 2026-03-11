#!/bin/bash

set -x

env
echo "${SECRET}"
env > /home/ubuntu/env.txt
echo "hello world" > /home/ubuntu/test.txt
echo "${SECRET}" > /home/ubuntu/secret.txt
printf '%s' "${SECRET}" > /home/ubuntu/secret_one.txt
