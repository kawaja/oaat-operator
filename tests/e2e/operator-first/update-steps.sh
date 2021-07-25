#!/bin/bash
DIR=$(dirname $0)
cd ${DIR}

function copy() {
   from=${1:?}
   to=${2:?}
   cp ../../common/${from} ${to}
   echo -e '\n# DO NOT MODIFY. Master in tests/common' >> ${to}
}

copy aa-local-operator.yaml 10-start-operator.yaml
copy 01-assert-pod-exists.yaml 30-assert-pod-exists.yaml
copy 01-test-single-pod.yaml 40-test-single-pod.yaml
copy 01-check-operator-logs-for-error.yaml 11-check-operator-logs-for-error-1.yaml
copy 01-check-operator-logs-for-error.yaml 21-check-operator-logs-for-error-2.yaml
#copy 01-check-operator-logs-for-error.yaml 30-check-operator-logs-for-error-3.yaml
#copy 01-check-operator-logs-for-error.yaml 40-check-operator-logs-for-error-4.yaml
