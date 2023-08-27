#!/bin/bash -e
dir=$(dirname $0)
cd ${dir}
dir=$(pwd)

skip_cluster_rebuild=
if [ "$1" = "--skip-cluster-rebuild" ]; then
   skip_cluster_rebuild=TRUE
   shift
fi

echo "--> building operator container"
export OPERATOR_TAG="kawaja.net/oaatoperator:e2e-$$"
(
   cd ..
   docker build --file build/Dockerfile --tag ${OPERATOR_TAG} .
)
echo "--> updating python dependencies"
python3 -m pip install --upgrade pip
pip --quiet install -r ../requirements/dev.txt

echo "--> cleaning up old files"
cd e2e
for dir in *; do
   if [ -d ${dir} ]; then
         ${dir}/update-steps.sh --cleanup
   fi
done

echo "-->validating YAML files"
find . -name '*.yaml' -print0 | xargs -0 -n 1 yq . > /dev/null
rm -f operator-output.log

echo "--> starting tests"
for dir in *; do
   if [ -d ${dir} ]; then
      if [ -f "${dir}/update-steps.sh" ]; then
         echo "**** setting up ${dir} test ****"
         if [ ! -x "${dir}/update-steps.sh" ]; then
            echo "file e2e/${dir}/update-steps.sh must be executable" >&2
            exit 1
         fi
         if [ -z $skip_cluster_rebuild ]; then
            k3d cluster delete ${dir}x || echo "delete failed (probably didn't exist), continuing"
            k3d cluster create ${dir}x
            docker pull busybox
            k3d image import --verbose --cluster ${dir}x busybox ${OPERATOR_TAG}
         fi
         kubectl config use-context k3d-${dir}x
         kubectl cluster-info
         ${dir}/update-steps.sh
         echo "**** running ${dir} test ****"
         sleep 60
         (cd ..; kubectl kuttl test --skip-delete --timeout 240 -v 4 --test ${dir})
         echo "**** cleaning up ${dir} test ****"
         k3d cluster delete ${dir}x
         ${dir}/update-steps.sh --cleanup
      fi
   fi
done
