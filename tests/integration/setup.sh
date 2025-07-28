#!/bin/bash
top=$(dirname $0)/../..
k3d cluster delete
k3d cluster create --k3s-arg '--kube-proxy-arg=conntrack-max-per-core=0@server:0'
kubectl apply -f ${top}/manifests/01-oaat-operator-crd.yaml 
kubectl apply -f ${top}/manifests/sample-oaat-type.yaml 
python3 -m pip install --upgrade pip
pip install -r ${top}/requirements/dev.txt
