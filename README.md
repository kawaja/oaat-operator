![master build](https://img.shields.io/github/workflow/status/kawaja/oaat-operator/Docker%20Image%20CI?label=master%20build)
![coverage](https://img.shields.io/badge/coverage-45%25-orange)
# oaat-operator
`oaat-operator` is a Kubernetes operator intended to manage a
group of tasks of which only one should be running at any time.
I make it available in case someone else is interested in using
such an operator.

## Features
* Define a list of items to run in a group – only one item
  in that group will run at a time.
* Each item is run in a Kubernetes pod.
* Pass the item name in an environment variable (OAAT_ITEM)
  or as a string substitution in the `command`, `args` or `env`
  of the pod's spec.
* Define the frequency an individual item will be run.
* Detect whether an item has succeeded or failed, based on
  the return value from the pod.
* Continue attempting to run an item until it succeeds.
* Track last failure and last success times for each item.
* Track the number of failures since the last success.
* Specify a cool-off period for an item which has failed (the
  item will not be selected to run again until the cool-off
  period has expired).

## Approach
`oaat-operator` is based on the [kopf](https://github.com/zalando-incubator/kopf)
framework and uses two Kubernetes
[Custom Resource Definitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/):
* OaatType – defines a type of item to be run and the definition of what
  'run' means. Currently `oaat-operator` only supports a `Pod` as mechanism to run an item.
* OaatGroup – defines a group of items which are to be run 'one at a time', including
  the frequency that each item should be run, cool-off timers for item failures, etc.

The operator keeps track of item failures and endeavours to retry failures
without blocking un-run items. The intention is to run each item approximately in line
with the `frequency` setting for the OaatGroup.

The operator sets up a timer on the OaatGroup and each time the timer triggers, it will then:
- if an item is currently running, quit the cycle to wait for the timer to expire again.
- if an item is not running, determine whether an item is ready to run and, if so, run it. 

The operator selects an item to run using the following algorithm:
- phase one: choose valid item candidates:
    - start with a list of all possible items to run
    - remove from the list items which have been successful within the
      period in the `frequency` setting in the OaatGroup
    - remove from the list items which have failed within the period
      in the `failureCoolOff` setting in the OaatGroup
- phase two: choose the item to run from the valid item candidates:
    - if there is just one item, choose it
    - find the item with the oldest success (or has never succeeded)
    - if there is just one item that is "oldest", choose it
    - of the items with the oldest success, find the item with the
      oldest failure
    - if there is just one item that has both the oldest success and
      the oldest failure, choose it
    - choose at random (this is likely to occur if no items have
      been run – i.e. first iteration)

## Quick Start
### Create the CRDs
```sh
kubectl apply -f manifests/01-oaat-operator-crd.yaml
```
This creates two CRDs: OaatType and OaatGroup.
### Create an OaatType
```yaml
apiVersion: kawaja.net/v1
kind: OaatType
metadata:
  name: oaattest
spec:
  type: pod
  podspec:
    container:
      name: test
      image: busybox
      command: ["sh", "-x", "-c"]
      args:
        - |
          echo "OAAT_ITEM={{oaat_item}}"
          sleep $(shuf -i 10-180 -n 1)
          exit $(shuf -i 0-1 -n 1)
```
This one sleeps for a random time (between 10 seconds and
3 minutes) and randomly succeeds (50%) or fails (50%).
### Create an OaatGroup
```yaml
apiVersion: kawaja.net/v1
kind: OaatGroup
metadata:
  name: testsimple-oaat
spec:
  frequency: 5m
  oaatType: oaattest
  oaatItems:
    - item1
    - item2
```
This creates two items, which will be run every 5 minutes.
### Start the operator
```sh
kubectl apply -f manifests/02-oaat-operator-deployment.yaml
```
### Watch item progress
```sh
kubectl get oaatgroup -w
```
## Limitations
* `oaat-operator` is not intended for precise timing of item start
  times – checking whether an item is ready to run occurs every
  30 seconds.
* Each item in the group will use the same pod specification
  (other than the string substitutions in the `command`, `args`
  or `env`.
* List of items is currently a fixed list specified in the OaatGroup.
* Item pods can only have a single container.
* Only tested on Kubernetes 1.18.

## Roadmap
* Documentation
* Blackout windows ([#2](https://github.com/kawaja/oaat-operator#2)) – time windows during which no items will be
  started. Potentially also provide an option where running items
  could be stopped during the blackout window.
* EachOnce ([#3](https://github.com/kawaja/oaat-operator#3)) – ensure each item runs once successfully and then stop.
* Exponential backoff ([#4](https://github.com/kawaja/oaat-operator#4)) – rather than just provide a fixed cool-off period
  exponentially increase the wait.
* Dynamic item list – use other mechanisms to create the list of items:
  * output of a container ([#5](https://github.com/kawaja/oaat-operator#5))
  * contents of a configmap ([#6](https://github.com/kawaja/oaat-operator#6))
  * result of an API call? ([#7](https://github.com/kawaja/oaat-operator#7))
* Schema validation ([#8](https://github.com/kawaja/oaat-operator#8)) – currently uses some spot checks of certain critical
  fields; instead, use json-schema to validate the CRD objects against
  a schema.
* Complete unit test suite ([#9](https://github.com/kawaja/oaat-operator#9))

## History
This started as a "spare time" COVID-19 lockdown project to improve
my knowledge of Python and the reliability and completeness of the
backups of my home lab.

Previously, I used a big script which sequentially backed up various
directories to cloud providers, however if the backup of a directory
failed, it would not retry and the issue would often be lost in
the logs. When a backup failure was detected, I could run the script
again, but it would re-run backups that had been successful already.

I decided I wanted to move to more of a continuous backup approach,
with smaller backup jobs which could be easily retried without
re-running successful backups.

The features evolved from there.
