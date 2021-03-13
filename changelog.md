# Changelog

## v0.5.7

* feature: %%oaat_item%% substitution now works in 'command' for pod
* bugfix: container build was not using requirements.txt versions
* build: use github action docker/build-push-action
* build: add LGTM, add badges
* build: add testing to github actions
* testing: add oaatgroup job/validation testing
* dependencies: kopf 0.27 -> 1.30.1
* dependencies: PyYAML 5.3.1 -> 5.4.1
* dependencies: pykube-ng 20.7.2 -> 21.3.0

## v0.5.6

Clean up various issues associated with generalising code and moving build to github.

* build: validate that version number of sample manifest files matches version.txt
* build: turn on dependabot
* build: add __version__, __gitsha__ and __build_date__ variables
* build: set :dev label on docker image for most recent build
* bugfix: retry initialisation if OaatGroup is created before its OaatType (and generally improve robustness of handlers)
* bugfix: fix login issue caused by the removal of the `kubernetes` package from container build
* dependencies: PyYAML 5.3 -> 5.3.1
