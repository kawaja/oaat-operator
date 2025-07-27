#!/bin/bash -e
DIR=$(dirname $0)
cd ${DIR}

. ../../common/update-steps.sh

step       00 error-if-pods-exist
step       01 start-operator
step       02 setup
step       11 check-operator-logs-for-error
local_step 20 add-oaatgroup
step       21 check-operator-logs-for-error
step       22 wait-60-seconds
local_step 24 check-for-validated-oaatgroup
local_step 25 check-for-accepted-oaatgroup
step       30 assert-pod-exists
step       31 check-operator-logs-for-error
step       40 test-single-pod
local_step 45 pause-job-run
step       46 trigger-item-success
step       50 check-operator-logs-for-error
step       99 teardown
