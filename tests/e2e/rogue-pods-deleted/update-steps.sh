#!/bin/bash
DIR=$(dirname $0)
cd ${DIR}

. ../../common/update-steps.sh

step 02 setup
#    03 add oaatgroup with item2 success
step 04 check-operator-logs-for-error
step 05 assert-item1-pod-exists
step 06 test-single-pod
#    10 create-item3-rogue
step 11 wait-60-seconds
step 12 assert-item1-pod-exists
step 13 test-single-pod
#    15 pause-job-run
step 20 trigger-item-success
step 30 check-operator-logs-for-error
