#!/bin/bash

sudo -H -u ubuntu bash -c 'echo "hello world" > /home/ubuntu/test.txt'
sudo -H --preserve-env=SECRET -u ubuntu bash -c  'echo "$SECRET" > /home/ubuntu/secret.txt'
