#!/bin/bash -e
top=$(dirname $0)/../..
k3d cluster delete
k3d cluster create --wait --no-lb --k3s-arg '--kube-proxy-arg=conntrack-max-per-core=0@server:0' --k3s-arg '--disable=metrics-server@server:*'

# Wait for cluster to be fully ready
#echo "Waiting for cluster to be ready..."
#kubectl wait --for=condition=Ready nodes --all --timeout=60s

echo "Waiting for system pods to be created..."
for i in {1..30}; do
   PODCNT=$(kubectl get pod -l k8s-app=kube-dns -n kube-system 2>/dev/null | wc -l)
   if [ ${PODCNT} -gt 0 ]; then
      echo "System pods created"
      break
   fi
   echo "  Waiting for system pods to be created... ($i/30)"
   sleep 2
done

# Wait for system pods to be ready (especially metrics-server)
echo "Waiting for system pods to be ready..."
# Wait up to 2 minutes for critical system pods
#kubectl wait --for=condition=Ready pod -l k8s-app=metrics-server -n kube-system --timeout=580s || echo "Metrics server not ready, continuing anyway"
kubectl wait --for=condition=Ready pod -l k8s-app=kube-dns -n kube-system --timeout=580s || echo "CoreDNS not ready, continuing anyway"

# Additional wait for metrics API to be available
#echo "Waiting for metrics API to be available..."
#for i in {1..30}; do
#  if kubectl get --raw "/apis/metrics.k8s.io/v1beta1" >/dev/null 2>&1; then
#    echo "Metrics API is ready"
#    break
#  fi
#  echo "Waiting for metrics API... ($i/30)"
#  sleep 2
#done

kubectl apply -f ${top}/manifests/01-oaat-operator-crd.yaml 
kubectl apply -f ${top}/manifests/sample-oaat-type.yaml 
python3 -m pip install --upgrade pip
pip install -r ${top}/requirements/dev.txt

echo "Cluster setup complete and ready for integration tests"
