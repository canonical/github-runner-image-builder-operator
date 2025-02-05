#!/bin/bash

sudo -H -u ubuntu bash -c 'echo "hello world" > /home/ubuntu/test.txt'
sudo -HE -u ubuntu bash -c  'echo "$TEST_SECRET" > /home/ubuntu/secret.txt'
