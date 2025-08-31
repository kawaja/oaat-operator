# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is `oaat-operator`, a Kubernetes operator that manages groups of tasks where only one task should run at a time ("One At A Time"). It's built using the [kopf](https://github.com/zalando-incubator/kopf) framework and uses two Custom Resource Definitions (CRDs):

- **OaatType** - defines what it means to "run" an item (currently only Pod execution is supported)
- **OaatGroup** - defines a group of items to be run one at a time, with frequency and failure handling

## Key Commands

### Testing
```bash
# Install CRDs first (required for most tests)
kubectl apply -f manifests/01-oaat-operator-crd.yaml

# Run unit tests (no k8s required)
. .venv/bin/activate && python3 -m pytest tests/unit/test_utility.py

# Run full test suite (requires k8s cluster)
. .venv/bin/activate && python3 -m pytest --cov=oaatoperator --cov-append --cov-report=term --cov-report=xml:cov.xml .

# Run specific test file
. .venv/bin/activate && python3 -m pytest tests/unit/test_oaatgroup.py
```

### Linting
```bash
# Syntax errors and undefined names (fails build)
. .venv/bin/activate && flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full linting (warnings only)
. .venv/bin/activate && flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

### Dependencies
```bash
# Install runtime dependencies
. .venv/bin/activate && pip install -r requirements.txt

# Install development dependencies
. .venv/bin/activate && pip install -r requirements/dev.txt
```

## Architecture

The operator follows an event-driven architecture using kopf handlers:

### Core Components
- **handlers.py** - Main kopf event handlers for CRD objects and Pod lifecycle events
- **overseer.py** - Base class for managing objects under kopf handlers, provides common functionality
- **oaatgroup.py** - Manages OaatGroup resources and item selection logic
- **oaattype.py** - Manages OaatType resources
- **oaatitem.py** - Represents individual items within a group
- **pod.py** - Handles Pod creation and lifecycle management
- **runtime_stats.py** - Job runtime statistics collection and prediction using reservoir sampling
- **utility.py** - Common utility functions (time handling, logging, etc.)

### Key Workflow
1. OaatGroup timer triggers every 60 seconds
2. If no item is running, the operator selects the next item to run using a priority algorithm:
   - Filter out items that ran successfully within `frequency` period
   - Filter out items that failed within `failureCoolOff` period
   - Select item with oldest success time, then oldest failure time, then random
3. Create a Pod to run the selected item
4. Monitor Pod completion and update item status

### Testing Architecture
- Unit tests use pytest with mocking for k8s API calls
- Integration tests require a real k8s cluster (k3s used in CI)
- End-to-end tests use KUTTL framework with YAML test definitions in `tests/e2e/`
- Common test utilities in `tests/common/` for setup, teardown, and assertions

## Development Notes

- Python 3.11+ required
- Uses type hints extensively with `typing_extensions`
- Kubernetes 1.30+ supported
- All k8s interactions go through pykube client
- Item names are passed to pods via `OAAT_ITEM` environment variable or string substitution in pod spec
- The operator maintains item failure counts and last success/failure timestamps
- Runtime statistics are stored per-item using reservoir sampling for bounded memory usage
- All files should have a trailing newline
- Blank lines should not have spaces
