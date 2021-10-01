#!/bin/bash -e
dir=$(dirname $0)
cd ${dir}
dir=$(pwd)
python3 -m pip install --upgrade pip
pip --quiet install -r ../requirements/dev.txt
find e2e -name '*.yaml' -print0 | xargs -0 -n 1 yq . > /dev/null
rm -f operator-output.log


#(cd e2e
#for dir in *; do
#   if [ -d ${dir} ]; then
#      ${dir}/update-steps.sh --cleanup
#      ${dir}/update-steps.sh
#   fi
#done)
#kubectl kuttl test
#(cd e2e
#for dir in *; do
#   if [ -d ${dir} ]; then
#      ${dir}/update-steps.sh --cleanup
#   fi
#done)

cd e2e
for dir in *; do
   if [ -d ${dir} ]; then
      k3d cluster create ${dir}x
      docker pull busybox
      k3d image import --cluster ${dir}x busybox
      kubectl config use-context k3d-${dir}x
      ${dir}/update-steps.sh --cleanup
      ${dir}/update-steps.sh
      sleep 60
      (cd ..; kubectl kuttl test --timeout 240 --test ${dir})
      k3d cluster delete ${dir}x
      ${dir}/update-steps.sh --cleanup
   fi
done
