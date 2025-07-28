# Like System Edge Cases Documentation

This document outlines all edge cases handled by the recipe like/unlike system and their expected behaviors.

## Input Validation Edge Cases

### Recipe ID Validation

**✅ Valid Recipe IDs:**
- Alphanumeric characters: `recipe123`, `recipe456`
- Underscores: `recipe_123`, `my_recipe`
- Hyphens: `recipe-123`, `test-recipe`
- Single character: `r`, `1`
- Maximum length (100 chars): `a` * 100

**❌ Invalid Recipe IDs:**
- Empty string: `""` → 400 "Recipe ID cannot be empty"
- Whitespace only: `"   "` → 400 "Recipe ID cannot be empty or whitespace"
- Too long: `"a" * 101` → 400 "Recipe ID too long (max 100 characters)"
- Invalid characters:
  - Special chars: `recipe@123` → 400 "Recipe ID contains invalid characters"
  - Spaces: `recipe 123` → 400 "Recipe ID contains invalid characters" 
  - Symbols: `recipe#123`, `recipe%123` → 400 "Recipe ID contains invalid characters"
- Path traversal: `../../etc/passwd` → 400 "Recipe ID contains invalid characters"
- XSS attempts: `<script>alert("xss")</script>` → 400 "Recipe ID contains invalid characters"
- Non-string types: `123`, `null` → 400 "Recipe ID must be a string"

### User ID Validation

**✅ Valid User IDs:**
- Alphanumeric: `user123`
- Underscores: `user_123`
- Hyphens: `user-123`
- Dots: `user.123`
- Email-like: `user@domain.com` (if properly encoded)

**❌ Invalid User IDs:**
- Empty/null → 400 "User ID is required"
- Too long (>100 chars) → 400 "User ID too long"
- Invalid characters → 400 "User ID contains invalid characters"

## User Status Edge Cases

### User Authentication
- **No JWT token** → 401 Unauthorized
- **Invalid JWT token** → 422 Unprocessable Entity  
- **Malformed Authorization header** → 401/422
- **User not found from token** → 404 "User not found"

### User Account Status
- **Deleted user** → 404 "User {id} has been deleted"
- **Banned user** → 403 "User {id} is banned"
- **Suspended user** → 403 "User {id} is suspended"
- **Inactive user** → 403 "User {id} account is not active"

## Recipe Status Edge Cases

### Recipe Existence
- **Non-existent recipe** → 404 "Recipe {id} does not exist"
- **Deleted recipe** → 404 "Recipe {id} has been deleted"

### Recipe Availability
- **Draft recipe** → 422 "Recipe {id} is still in draft"
- **Processing recipe** → 422 "Recipe {id} is still processing"
- **Private recipe (non-owner)** → 403 "Cannot like a private recipe you don't own"

### Recipe State Changes During Operation
- **Recipe deleted during transaction** → 404 "Recipe {id} was deleted during operation"
- **Recipe status changed during transaction** → 422 "Recipe {id} is not available"

## Database Edge Cases

### Transaction Failures
- **Database unavailable** → 500 "Firestore database not available"
- **Transaction aborted** → 500 "Transaction was aborted due to conflicts"
- **Database timeout** → 500 "Database operation timed out"
- **Connection failures** → 500 "Failed to update like status"

### Data Integrity Issues
- **Negative likes_count** → Auto-corrected to 0 with warning log
- **Missing likes_count field** → Defaults to 0
- **Corrupted recipe data** → 404 "Could not verify recipe exists"

## Request Format Edge Cases

### HTTP Headers
- **Missing Authorization** → 401 Unauthorized
- **Invalid Content-Type** → 400 "Content-Type must be application/json"
- **Malformed Authorization header** → 401/422

### JSON Payload (POST requests)
- **Malformed JSON** → 400 "Invalid JSON format in request body"
- **Non-object JSON** → 400 "JSON payload must be an object"
- **Large JSON payload** → Graceful handling (ignored or 413/500)

## Concurrency Edge Cases

### Race Conditions
- **Recipe deletion during like operation** → 404 with transaction rollback
- **Multiple simultaneous likes** → Only one succeeds (idempotent)
- **Conflicting transactions** → Automatic retry via Firestore transaction system

### Performance Under Load
- **100+ concurrent operations** → All handled successfully with proper queuing
- **Response time degradation** → Operations timeout after 10 seconds

## Idempotency Edge Cases

### Like Operations
- **Multiple likes from same user** → likes_count remains 1
- **Like already-liked recipe** → Returns current state, no change
- **Unlike never-liked recipe** → Returns current state, no change

### Data Consistency
- **likes_count doesn't match actual likes** → Maintained via transactions
- **Orphaned like documents** → Prevented by transaction atomicity

## Error Response Format

All error responses follow consistent format:

```json
{
  "error": "Error Category",
  "message": "Human-readable description",
  "details": {} // Optional, for validation errors
}
```

### HTTP Status Code Mapping

| Status | Category | Examples |
|--------|----------|----------|
| 400 | Invalid Input | Malformed recipe ID, invalid JSON |
| 401 | Unauthorized | Missing/invalid JWT token |
| 403 | Permission Denied | Banned user, private recipe |
| 404 | Not Found | Non-existent recipe/user |
| 422 | Unprocessable Entity | Draft recipe, processing recipe |
| 500 | Server Error | Database failures, unexpected errors |

## Testing Edge Cases

### Unit Tests
```bash
# Test input validation
python -m pytest tests/controllers/test_like_edge_cases.py::TestLikeServiceEdgeCases -v

# Test controller error handling  
python -m pytest tests/controllers/test_like_edge_cases.py::TestLikeControllerEdgeCases -v
```

### Manual Testing
```bash
# Test malformed recipe ID
curl -X POST "http://localhost:5000/api/recipes/invalid@recipe/like" \
     -H "Authorization: Bearer YOUR_TOKEN"

# Test malformed JSON
curl -X POST "http://localhost:5000/api/recipes/recipe123/like" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"invalid": json}'

# Test without authorization
curl -X POST "http://localhost:5000/api/recipes/recipe123/like"
```

## Production Monitoring

### Key Metrics to Monitor
- **Input validation errors** (400 responses)
- **Permission denied errors** (403 responses)  
- **Recipe not found errors** (404 responses)
- **Database transaction failures** (500 responses)
- **Response time distribution** under load

### Alert Thresholds
- **Error rate > 5%** → Investigate input validation
- **404 rate > 10%** → Check recipe cleanup processes
- **500 rate > 1%** → Database health check
- **Average response time > 200ms** → Performance investigation

## Security Considerations

### Input Sanitization
- All recipe IDs and user IDs are validated against strict regex patterns
- Path traversal attempts are blocked
- XSS attempts in IDs are rejected
- SQL injection is prevented by Firestore's NoSQL nature

### Access Control
- Private recipes are protected from unauthorized likes
- User status (banned/suspended) is checked
- JWT token validation prevents unauthorized access

### Rate Limiting
- Future enhancement: Implement per-user rate limiting
- Database transaction limits provide natural throttling
- Large payload rejection prevents resource exhaustion 