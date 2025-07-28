# Like Service Load Testing Guide

This document explains how to run concurrency and load tests for the recipe like/unlike system.

## Test Categories

### 1. Unit Concurrency Tests
Located in `tests/services/test_like_concurrency.py`

**Purpose**: Test transaction safety and data integrity with mocked Firestore

**Tests included**:
- `test_concurrent_likes_same_recipe_same_user`: Idempotency verification (50 concurrent operations)
- `test_concurrent_likes_same_recipe_different_users`: Multi-user concurrency (100 users)
- `test_concurrent_like_unlike_oscillation`: Rapid like/unlike switching (100 operations)
- `test_stress_test_mixed_operations`: Comprehensive mixed operations (200 total operations)
- `test_response_time_under_load`: Performance benchmarking

**Run all concurrency tests**:
```bash
python -m pytest tests/services/test_like_concurrency.py -v
```

**Run specific test**:
```bash
python -m pytest tests/services/test_like_concurrency.py::TestLikeConcurrency::test_stress_test_mixed_operations -v -s
```

### 2. Integration Concurrency Tests
Located in `tests/integration/test_like_concurrency_integration.py`

**Purpose**: Test actual service logic with realistic mock Firestore behavior

**Tests included**:
- `test_concurrent_likes_data_integrity`: 20 concurrent users on same recipe
- `test_concurrent_like_unlike_same_user`: Oscillating operations from single user

**Run integration tests**:
```bash
python -m pytest tests/integration/test_like_concurrency_integration.py -v
```

### 3. HTTP Load Testing
Located in `scripts/like_load_test.py`

**Purpose**: Test actual HTTP endpoints under concurrent load

**Features**:
- Async HTTP requests using aiohttp
- Configurable number of users and operations
- Performance metrics (response times, throughput)
- Data integrity verification

**Basic usage**:
```bash
python scripts/like_load_test.py --users 50 --recipe test_recipe_123
```

**Full options**:
```bash
python scripts/like_load_test.py \
  --url http://localhost:5000 \
  --token YOUR_JWT_TOKEN \
  --users 100 \
  --operations 200 \
  --recipe your_recipe_id \
  --test both
```

**Available test types**:
- `concurrent`: Multiple users liking same recipe
- `oscillation`: Rapid like/unlike from same user  
- `both`: Run both tests sequentially

## Expected Results

### Data Integrity Assertions
✅ **likes_count accuracy**: Final count should equal number of unique users who liked
✅ **No negative counts**: likes_count should never go below 0
✅ **Idempotency**: Multiple likes from same user should not increase count
✅ **Consistency**: User like status should match recipe likes_count

### Performance Targets
✅ **Average response time**: < 100ms under normal load
✅ **95th percentile**: < 200ms for production readiness
✅ **Throughput**: > 50 requests/second for concurrent operations
✅ **No timeout errors**: All operations should complete within 10s

## Troubleshooting

### Common Issues

**1. Import errors**
```bash
# Add project root to Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/reciplan-backend"
```

**2. Missing dependencies**
```bash
pip install aiohttp  # For load testing script
```

**3. Firebase authentication errors**
- Unit tests: Use mocked Firestore (no credentials needed)
- Integration tests: Require proper Firebase setup
- HTTP tests: Need running Flask app with valid JWT tokens

### Test Development

**Adding new concurrency tests**:
1. Extend `TestLikeConcurrency` class in `test_like_concurrency.py`
2. Use `ThreadPoolExecutor` for concurrent operations
3. Verify data integrity with assertions
4. Include performance measurements

**Mock patterns**:
- Use shared state with threading locks for realistic concurrency simulation
- Mock Firestore transactions to test business logic
- Simulate database latency for performance testing

## Production Deployment

Before deploying like functionality:

1. **Run full test suite**:
   ```bash
   python -m pytest tests/services/test_like_concurrency.py tests/integration/test_like_concurrency_integration.py -v
   ```

2. **Load test against staging**:
   ```bash
   python scripts/like_load_test.py --url https://staging.yourapp.com --users 200 --test both
   ```

3. **Monitor key metrics**:
   - Transaction success rate > 99.9%
   - Average response time < 100ms
   - 95th percentile < 200ms
   - Zero data integrity violations

## Test Results Example

```
✅ Stress test completed: 200 operations, final likes_count: 35, unique users who liked: 35

📊 Performance Statistics:
   - Total test time: 2.45s
   - Throughput: 81.6 requests/second
   - Response times:
     • Average: 45.2ms
     • Min: 12.1ms
     • Max: 156.3ms
     • 50th percentile: 42.1ms
     • 95th percentile: 98.7ms
     • 99th percentile: 134.2ms
``` 