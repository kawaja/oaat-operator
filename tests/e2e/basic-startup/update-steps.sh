#!/bin/bash
DIR=$(dirname $0)
cd ${DIR}

. ../../common/update-steps.sh

step 02 setup
step 11 check-operator-logs-for-error
#    20 add oaatgroup
step 21 check-operator-logs-for-error
#    22 check for validated oaatgroup
#    23 check for accepted oaatgroup
step 30 assert-pod-exists
step 31 check-operator-logs-for-error
step 40 test-single-pod
#    45 pause-job-run
step 46 trigger-item-success
step 50 check-operator-logs-for-error
