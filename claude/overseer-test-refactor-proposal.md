# Overseer Test Refactor Proposal

## Overview

This document outlines the proposal to split `test_overseer.py` into separate unit and integration test files to improve test maintainability, execution speed, and development workflow.

## Current State Analysis

The current `test_overseer.py` contains a single integration test (`test_kopfrunner`) that:
- Uses `KopfRunner` to execute the real operator (`tests/operator_overseer.py`)
- Creates actual Kubernetes pods in k3d cluster
- Tests all Overseer functionality end-to-end
- Validates both behavior and log output patterns
- Takes significant time to execute due to Kubernetes API calls

### Test Coverage Analysis

The current test validates these Overseer methods:
1. **Constructor validation** - Ensures required kwargs are provided
2. **Logging methods** - `error()`, `warning()`, `info()`, `debug()`
3. **Status management** - `get_status()`, `set_status()`
4. **Label retrieval** - `get_label()`
5. **Kubernetes operations** - `get_kubeobj()`, `delete()`
6. **Annotation handling** - `set_annotation()`
7. **Exception handling** - `handle_processing_complete()`

## Proposed Split

### 1. Unit Tests (`tests/unit/test_overseer_unit.py`)

**Purpose**: Test individual Overseer methods with full mocking  
**Approach**: Mock all external dependencies (pykube, kopf, logging)

#### Test Categories:
- **Constructor validation**: Test kwargs checking and error handling
- **Logging methods**: Verify calls to logger with correct levels
- **Status management**: Test get/set operations with mocked patch object
- **Label retrieval**: Test label access with mocked meta object
- **Kubernetes object operations**: Mock pykube interactions
- **Annotation handling**: Test annotation setting with mocked patch
- **Exception handling**: Test ProcessingComplete handling logic

#### Benefits:
- Fast execution (~seconds)
- No Kubernetes cluster required
- Isolated testing of business logic
- Easy to test error conditions and edge cases
- Deterministic test results
- CI-friendly for every commit

### 2. Integration Tests (`tests/integration/test_overseer_integration.py`)

**Purpose**: Test Overseer functionality in real Kubernetes environment  
**Approach**: Keep existing k3d + KopfRunner pattern

#### Test Scenarios:
- Full operator lifecycle with real pods
- Actual Kubernetes API interactions
- Real annotation/status patching behavior
- Pod creation, update, deletion flows
- Log output validation from real operator execution
- End-to-end kopf framework integration

#### Benefits:
- Validates real-world behavior
- Tests Kubernetes API integration
- Catches environment-specific issues
- Ensures kopf framework integration works
- Validates actual pod lifecycle management

## Recommended File Structure

```
tests/
├── unit/
│   ├── __init__.py
│   ├── test_overseer_unit.py          # Mocked unit tests
│   └── conftest.py                    # Unit test fixtures & mocks
├── integration/
│   ├── __init__.py
│   ├── test_overseer_integration.py   # K3d integration tests
│   ├── operator_overseer.py           # Test operator (moved from tests/)
│   └── conftest.py                    # Integration test fixtures
└── conftest.py                        # Shared fixtures
```

## Test Execution Strategy

### Local Development
- **Unit tests**: Run on every save/commit (fast feedback)
- **Integration tests**: Run manually or on significant changes

### CI/CD Pipeline
- **Pull Request stage**: Run unit tests only (fast feedback)
- **Merge to main**: Run both unit and integration tests
- **Pytest markers**: `@pytest.mark.unit` and `@pytest.mark.integration`

### Pytest Configuration
```ini
[pytest]
markers =
    unit: Unit tests with mocking
    integration: Integration tests requiring k3d
testpaths = tests
```

### Example Commands
```bash
# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run all tests
pytest
```

## Implementation Benefits

1. **Development Speed**: Fast unit test feedback loop
2. **CI Efficiency**: Reduced build times with unit-only CI runs
3. **Test Reliability**: Unit tests less prone to flaky failures
4. **Coverage Clarity**: Separate validation of logic vs. integration
5. **Maintenance**: Easier to debug and maintain focused test suites
6. **Cost Reduction**: Less k3d cluster usage in CI

## Migration Plan

1. Create new directory structure
2. Write comprehensive unit tests with mocks
3. Move existing integration test to new location
4. Update pytest configuration
5. Update GitHub workflows to run unit tests in PR stage
6. Update documentation and README

## Dependencies

- `pytest-mock`: For comprehensive mocking capabilities
- `unittest.mock`: Python standard library mocking
- Existing `kopf.testing.KopfRunner` for integration tests
- k3d cluster for integration test environment

This refactoring will provide both fast feedback through unit tests and comprehensive validation through integration tests, improving the overall development experience.