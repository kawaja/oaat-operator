#!/bin/bash
dir=$(dirname $0)/..
k3d cluster delete
k3d cluster create --k3s-server-arg '--kube-proxy-arg=conntrack-max-per-core=0' --k3s-agent-arg '--kube-proxy-arg=conntrack-max-per-core=0'
kubectl apply -f ${dir}/manifests/01-oaat-operator-crd.yaml 
kubectl apply -f ${dir}/manifests/sample-oaat-type.yaml 
python3 -m pip install --upgrade pip
pip install -r ${dir}/requirements/dev.txt
