#!/bin/bash -e
DIR=$(dirname $0)
cd ${DIR}

. ../../common/update-steps.sh

step       00 error-if-pods-exist
step       01 start-operator
step       02 setup
local_step 03 add-oaatgroup-with-item2-success
step       04 check-operator-logs-for-error
step       05 assert-item1-pod-exists
step       06 test-single-pod
local_step 10 create-item3-rogue
step       11 wait-120-seconds
step       12 assert-item1-pod-exists
step       13 test-single-pod
local_step 15 pause-job-run
step       20 trigger-item-success
step       30 check-operator-logs-for-error
step       99 teardown
