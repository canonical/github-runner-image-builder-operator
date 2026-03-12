#!/bin/bash

set -x

env
echo "${SECRET}"
printenv > /home/ubuntu/env.txt
(set -o posix ; set) > /home/ubuntu/posix.txt
echo "hello world" > /home/ubuntu/test.txt
echo "${SECRET}" > /home/ubuntu/secret.txt
printf '%s' "${SECRET}" > /home/ubuntu/secret_one.txt
echo "hello world" > /home/ubuntu/test_two.txt
sync
