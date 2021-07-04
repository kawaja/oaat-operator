#!/bin/bash
dir=$(dirname $0)/..
k3d cluster delete
k3d cluster create
kubectl apply -f ${dir}/manifests/01-oaat-operator-crd.yaml 
kubectl apply -f ${dir}/manifests/sample-oaat-type.yaml 
python3 -m pip install --upgrade pip
pip install -r ${dir}/requirements/dev.txt
