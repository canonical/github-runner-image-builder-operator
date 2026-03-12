#!/bin/bash

set -x

env
echo "${SECRET}"
sudo -H -u ubuntu 'printenv > /home/ubuntu/env.txt'
sudo -H -u ubuntu bash -c 'printenv > /home/ubuntu/env-one.txt'
sudo -H -u ubuntu bash -c '(set -o posix ; set) > /home/ubuntu/posix.txt'
sudo -H -u ubuntu bash -c 'echo "hello world" > /home/ubuntu/test.txt'
sudo -H --preserve-env=SECRET -u ubuntu 'echo "${SECRET}" > /home/ubuntu/secret.txt'
sudo sync
sudo -H -u sync
