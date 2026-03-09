#!/bin/bash

sudo -H -u ubuntu bash -c 'echo "hello world" > /home/ubuntu/test.txt'
sudo -H --preserve-env=TEST_SECRET -u ubuntu bash -c  'echo "$TEST_SECRET" > /home/ubuntu/secret.txt'
