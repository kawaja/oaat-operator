# Testing Guide for oaat-operator

This guide covers testing strategies for the oaat-operator project, including local testing and CI simulation.

## Quick Start

```bash
# Run all tests in CI-like environment (recommended before pushing)
make test-ci-local

# Run unit tests locally (fast development)
make test-unit

# Run linting checks locally
make lint
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Purpose**: Fast, isolated testing of business logic
- **Requirements**: None (fully mocked)
- **Runtime**: ~2 seconds for 169 tests
- **Coverage**: All business logic, error handling, edge cases

### Integration Tests (`tests/integration/`)
- **Purpose**: Real Kubernetes API validation
- **Requirements**: k3d cluster + CRDs installed
- **Runtime**: ~30 seconds for 5 tests
- **Coverage**: Pod creation, CRD functionality, API connectivity

## Local Development Testing

### Fast Unit Testing
```bash
# Run unit tests (no k3d required)
make test-unit
# or
source .venv/bin/activate && pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_oaattype.py -v

# Run with coverage
pytest tests/unit/ --cov=oaatoperator --cov-report=term
```

### Integration Testing
```bash
# Requires k3d cluster setup
kubectl apply -f manifests/01-oaat-operator-crd.yaml
kubectl apply -f manifests/sample-oaat-type.yaml

# Run integration tests
make test-integration
# or
pytest tests/integration/ -v
```

### Linting
```bash
# Run linting checks
make lint
# or
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

## CI Simulation with Docker

### Why Use Docker Testing?

The Docker testing environment simulates GitHub Actions CI environment:

- ✅ **No kubeconfig files** (like GitHub Actions)
- ✅ **Clean Ubuntu environment** (ubuntu-22.04)
- ✅ **Isolated dependencies** (no interference from local setup)
- ✅ **CI environment variables** (`GITHUB_ACTIONS=true`, `CI=true`)
- ✅ **Same Python version** (Python 3.11)

### Docker Testing Commands

```bash
# Complete CI simulation (recommended before pushing)
make test-ci-local

# Individual Docker test services
make test-docker-unit      # Unit tests only
make test-docker-lint      # Linting only
make test-docker-coverage  # Unit tests with coverage

# Interactive debugging
make debug-docker          # Shell access to test environment
```

### Manual Docker Usage

```bash
# Build test environment
docker-compose -f docker-compose.test.yml build

# Run specific tests
docker-compose -f docker-compose.test.yml run --rm unit-tests
docker-compose -f docker-compose.test.yml run --rm lint-check

# Interactive shell for debugging
docker-compose -f docker-compose.test.yml run --rm debug

# Clean up
make clean-docker
```

## GitHub Actions Workflow

Our CI pipeline runs the following steps:

1. **Lint Check**: `flake8` for syntax errors and code style
2. **Unit Tests**: 169 tests with global pykube mocking
3. **Coverage Report**: Uploaded to codecov

**Key Feature**: No k3d cluster required for CI due to comprehensive mocking.

## Testing Best Practices

### Before Pushing to GitHub

1. **Run CI simulation locally**:
   ```bash
   make test-ci-local
   ```

2. **Verify all tests pass** in clean environment

3. **Check linting** passes without errors

### During Development

1. **Use unit tests** for fast feedback:
   ```bash
   make test-unit
   ```

2. **Run specific tests** for focused development:
   ```bash
   pytest tests/unit/test_oaattype.py::BasicTests::test_podspec -v
   ```

3. **Use integration tests** for major changes:
   ```bash
   make test-integration  # After setting up k3d
   ```

## Troubleshooting

### Common Issues

**"No module named 'pytest'"**
```bash
# Install dev dependencies
pip install -r requirements/dev.txt
```

**"pykube.KubeConfig.from_env() failed"**
- This should not happen in unit tests due to global mocking
- If it occurs, check that `mock_pykube_global` fixture is working
- Use Docker testing to isolate the issue

**Integration tests fail**
```bash
# Ensure CRDs are installed
kubectl apply -f manifests/01-oaat-operator-crd.yaml
kubectl apply -f manifests/sample-oaat-type.yaml

# Check k3d cluster status
kubectl get nodes
```

### Docker Issues

**"Docker not found"**
```bash
# Install Docker and docker-compose
sudo apt-get update
sudo apt-get install docker.io docker-compose
```

**Permission denied**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

## Mock Infrastructure

### Global pykube Mocking

All unit tests automatically get pykube mocking via `@pytest.fixture(autouse=True)`:

- `pykube.KubeConfig.from_env()` → Mock config object
- `pykube.KubeConfig.from_file()` → Mock config object
- `pykube.HTTPClient()` → Mock HTTP client

### Context Manager Mocking

```python
# Kubernetes object mocking
with KubeObject(KubeOaatType, test_spec):
    ot = OaatType('test-name')  # Works with mocked API

# Pod mocking with query support
with KubeObjectPod(pod_spec) as pod:
    og.verify_running()  # Finds pods via filtered queries
```

### Test Coverage

- **169 unit tests**: Full business logic coverage with mocks
- **5 integration tests**: Real k3d cluster validation
- **Zero k3d dependencies**: Unit tests run in any environment
- **CI-friendly**: Fast feedback with comprehensive validation

## Performance

- **Unit tests**: ~2 seconds (169 tests)
- **Integration tests**: ~30 seconds (5 tests)
- **Docker CI simulation**: ~3-5 minutes (full pipeline)
- **GitHub Actions**: ~4 minutes (vs ~54 minutes before optimization)
