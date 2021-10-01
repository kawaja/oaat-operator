#!/bin/bash
DIR=$(dirname $0)
cd ${DIR}

. ../../common/update-steps.sh

step 02 setup
#    03 add oaatgroup with item2 success
step 04 check-operator-logs-for-error
step 05 assert-item1-pod-exists
step 06 test-single-pod
step 10 trigger-item-success
step 11 wait-60-seconds
step 12 assert-item2-pod-exists
step 13 test-single-pod
step 20 trigger-item-success
step 21 wait-60-seconds
step 22 assert-oaatgroup-status-idle
step 23 check-operator-logs-for-no-jobs
step 24 wait-60-seconds
step 25 error-if-pods-exist
#    30 pause-job-run
step 40 check-operator-logs-for-error
