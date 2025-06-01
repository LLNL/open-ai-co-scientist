# AI Co-Scientist Tests

This directory contains all test files for the AI Co-Scientist project.

## Test Structure

```
tests/
├── __init__.py                 # Makes tests a Python package
├── README.md                   # This file
├── test_database.py           # Database and arXiv tracking tests
├── test_agents.py             # Agent functionality tests
├── test_arxiv.py              # arXiv search integration tests
├── test_similarity.py         # Hypothesis similarity tests
├── test_new_endpoints.py      # API endpoint verification tests
├── verify_endpoints.py        # Endpoint verification utility
├── test_visjs_graph.py        # Graph visualization tests
└── test_graph.html           # HTML test file for graph visualization
```

## Running Tests

### Individual Test Files

Run specific test modules:

```bash
# Database and arXiv tracking tests
python tests/test_database.py

# Agent functionality tests  
python tests/test_agents.py

# arXiv search integration tests
python tests/test_arxiv.py

# API endpoint verification
python tests/test_new_endpoints.py
```

### All Tests

Run all tests using unittest discovery:

```bash
# From project root
python -m unittest discover tests/ -v

# Or using pytest if installed
pytest tests/ -v
```

### Test Coverage

To run tests with coverage (requires `coverage` package):

```bash
pip install coverage
coverage run -m unittest discover tests/
coverage report
coverage html  # Generates HTML coverage report
```

## Test Categories

### 1. Database Tests (`test_database.py`)
- Database initialization and schema creation
- Session management
- Hypothesis persistence
- arXiv paper storage and tracking
- Search history logging
- Paper-hypothesis relationships
- Analytics and reporting
- Data export functionality

### 2. Agent Tests (`test_agents.py`)
- Hypothesis generation with arXiv reference tracking
- Reflection agent arXiv citation extraction
- Database integration with agents
- Reference pattern matching
- End-to-end agent workflows

### 3. arXiv Integration Tests (`test_arxiv.py`)
- Basic arXiv search functionality
- Paper detail retrieval
- Category-based searches
- Recent paper searches
- Search result formatting
- Database logging integration

### 4. API Tests (`test_new_endpoints.py`)
- Endpoint registration verification
- Request/response validation
- Error handling
- Authentication (if implemented)

### 5. Utility Tests
- `test_similarity.py`: Hypothesis similarity calculations
- `test_visjs_graph.py`: Graph visualization functionality
- `verify_endpoints.py`: Static endpoint verification

## Test Data

Tests use temporary databases and mock arXiv API responses to avoid:
- Dependency on external services
- Pollution of production data
- Network-related test failures

## Mocking Strategy

Tests mock external dependencies:
- arXiv API calls using `unittest.mock`
- LLM API calls for reproducible results
- File system operations for isolation
- Network requests for reliability

## Continuous Integration

These tests are designed to run in CI environments with:
- No external dependencies
- Isolated test databases
- Deterministic outcomes
- Comprehensive coverage

## Contributing

When adding new functionality:

1. **Add corresponding tests** in the appropriate test file
2. **Use proper mocking** for external dependencies
3. **Follow naming conventions**: `test_<functionality_name>`
4. **Include docstrings** explaining what each test verifies
5. **Test both success and failure cases**
6. **Update this README** if adding new test categories

## Test Dependencies

Required packages for running tests:
- `unittest` (built-in)
- `tempfile` (built-in) 
- `unittest.mock` (built-in)
- `sqlite3` (built-in)

Optional packages:
- `pytest` - Alternative test runner
- `coverage` - Test coverage reporting
- `pytest-cov` - Coverage plugin for pytest

## Debugging Tests

For debugging failed tests:

```bash
# Run with verbose output
python -m unittest tests.test_database -v

# Run specific test method
python -m unittest tests.test_database.TestDatabaseManager.test_create_session -v

# Use pdb for debugging
python -m pdb tests/test_database.py
```

## Performance Testing

For performance-related tests:

```bash
# Time test execution
time python tests/test_database.py

# Profile test execution
python -m cProfile tests/test_database.py
```

This test suite ensures the reliability and correctness of the AI Co-Scientist system, particularly the new arXiv tracking and database persistence features.