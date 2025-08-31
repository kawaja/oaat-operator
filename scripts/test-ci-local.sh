#!/bin/bash
# test-ci-local.sh - Local CI environment testing script
set -e

echo "🐳 Setting up local CI environment for testing..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to run a test service and report results
run_test() {
    local service_name=$1
    local description=$2

    echo -e "\n${BLUE}🧪 Running: ${description}${NC}"
    echo "Service: docker-compose -f docker-compose.test.yml run --rm ${service_name}"

    if docker-compose -f docker-compose.test.yml run --rm ${service_name}; then
        echo -e "${GREEN}✅ ${description} - PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ ${description} - FAILED${NC}"
        return 1
    fi
}

# Ensure Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose is not installed or not in PATH${NC}"
    exit 1
fi

# Build the test image
echo -e "${BLUE}🔨 Building test environment...${NC}"
if ! docker-compose -f docker-compose.test.yml build; then
    echo -e "${RED}❌ Failed to build test environment${NC}"
    exit 1
fi

# Create coverage directory
mkdir -p coverage-reports

# Track test results
failed_tests=0

# Run linting (mimics GitHub Actions lint step)
if ! run_test "lint-check" "Linting checks"; then
    ((failed_tests++))
fi

# Run unit tests (mimics GitHub Actions unit test step)
if ! run_test "unit-tests" "Unit tests"; then
    ((failed_tests++))
fi

# Run unit tests with coverage (mimics GitHub Actions coverage step)
if ! run_test "unit-tests-coverage" "Unit tests with coverage"; then
    ((failed_tests++))
fi

# Summary
echo -e "\n${BLUE}📊 Test Summary${NC}"
if [ $failed_tests -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Your changes are ready for GitHub Actions.${NC}"
    echo -e "${GREEN}✅ Linting: PASSED${NC}"
    echo -e "${GREEN}✅ Unit tests: PASSED${NC}"
    echo -e "${GREEN}✅ Coverage: PASSED${NC}"
else
    echo -e "${RED}💥 ${failed_tests} test suite(s) failed.${NC}"
    echo -e "${YELLOW}💡 Fix these issues before pushing to GitHub.${NC}"
fi

# Show coverage report if available
if [ -f coverage-reports/cov.xml ]; then
    echo -e "\n${BLUE}📈 Coverage report generated: coverage-reports/cov.xml${NC}"
fi

echo -e "\n${BLUE}🛠️  Debugging options:${NC}"
echo "  Interactive shell: docker-compose -f docker-compose.test.yml run --rm debug"
echo "  View logs: docker-compose -f docker-compose.test.yml logs"
echo "  Clean up: docker-compose -f docker-compose.test.yml down --rmi local"

exit $failed_tests
