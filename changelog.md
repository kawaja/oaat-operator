## v0.5.6

Clean up various issues associated with generalising code and moving build to github.

* build: validate that version number of sample manifest files matches version.txt
* build: turn on dependabot
* build: add __version__, __gitsha__ and __build_date__ variables
* build: set :dev label on docker image for most recent build
* bugfix: retry initialisation if OaatGroup is created before its OaatType (and generally improve robustness of handlers)
* bugfix: fix login issue caused by the removal of the `kubernetes` package from container build
* dependencies: PyYAML 5.3 -> 5.3.1
