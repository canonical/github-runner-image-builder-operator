#!/bin/bash

# This script is not directly used in the integration tests.
# Modify the TESTDATA_TEST_SCRIPT_URL variable in the test code to point to this script on GitHub 
# to change the script in the test.

sudo -H -u ubuntu bash -c 'echo "hello world" > /home/ubuntu/test.txt'
sudo -H --preserve-env=SECRET -u ubuntu bash -c 'echo "$SECRET" > /home/ubuntu/secret.txt'
