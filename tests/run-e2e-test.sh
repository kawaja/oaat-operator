#!/bin/bash -e
dir=$(dirname $0)
dir=$(cd ${dir}; pwd)
cd ${dir}/..
if [ "${1}" != "--nocluster" ]; then
   k3d cluster delete
   k3d cluster create
fi
python3 -m pip install --upgrade pip
pip --quiet install -r requirements/dev.txt
cd ${dir}
find e2e -name '*.yaml' -print0 | xargs -0 -n 1 yq . > /dev/null
rm -f operator-output.log
e2e/operator-first/update-steps.sh
kubectl kuttl test
