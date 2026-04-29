# API Documentation

## Base URL

- **Development**: `http://localhost:8000/api/v1`
- **Production**: `https://your-deployed-url.com/api/v1`

## Authentication

Currently, no authentication is required (for demo purposes). In production, implement JWT or token-based authentication.

## Merchant Endpoints

### Get All Merchants

```
GET /merchants/
```

**Response** (200 OK):
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Acme Digital Services",
      "email": "accounting@acme-digital.in",
      "balance_paise": 100000,
      "held_balance_paise": 60000,
      "available_balance_paise": 40000,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Get Merchant Details

```
GET /merchants/{id}/
```

**Parameters**:
- `id` (UUID): Merchant ID

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Digital Services",
  "email": "accounting@acme-digital.in",
  "balance_paise": 100000,
  "held_balance_paise": 60000,
  "available_balance_paise": 40000,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Get Merchant Balance

```
GET /merchants/{id}/balance/
```

**Parameters**:
- `id` (UUID): Merchant ID

**Response** (200 OK):
```json
{
  "total_paise": 100000,
  "held_paise": 60000,
  "available_paise": 40000
}
```

### Get Merchant Ledger (Credits/Debits)

```
GET /merchants/{id}/ledger/
```

**Parameters**:
- `id` (UUID): Merchant ID
- `page` (integer): Page number (default: 1)

**Response** (200 OK):
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "650e8400-e29b-41d4-a716-446655440001",
      "amount_paise": 500000,
      "entry_type": "credit",
      "description": "Payment from TechCorp USA",
      "created_at": "2024-01-15T09:00:00Z"
    }
  ]
}
```

## Payout Endpoints

### Create Payout Request

```
POST /payouts/
Headers: Idempotency-Key: {uuid}
```

**Required Headers**:
- `Idempotency-Key`: UUID string (unique per merchant, 24-hour expiry)

**Request Body**:
```json
{
  "merchant_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount_paise": 50000,
  "bank_account_id": "ACCOUNT_123456"
}
```

**Responses**:

**201 Created** (new payout created):
```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "merchant": "550e8400-e29b-41d4-a716-446655440000",
  "amount_paise": 50000,
  "bank_account_id": "ACCOUNT_123456",
  "status": "pending",
  "attempt_count": 0,
  "error_message": "",
  "created_at": "2024-01-15T11:00:00Z",
  "completed_at": null
}
```

**200 OK** (duplicate request, same idempotency key):
Returns the same response as the original request.

**400 Bad Request** (validation error):
```json
{
  "error": "Insufficient balance. Available: 40000 paise, Requested: 50000 paise"
}
```

**Errors**:
- Missing `Idempotency-Key` header
- `merchant_id` not found
- `amount_paise` <= 0
- `bank_account_id` empty
- Insufficient balance (taking held payouts into account)

### Get Payout Details

```
GET /payouts/{id}/
```

**Parameters**:
- `id` (UUID): Payout ID

**Response** (200 OK):
```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "merchant": "550e8400-e29b-41d4-a716-446655440000",
  "merchant_name": "Acme Digital Services",
  "amount_paise": 50000,
  "bank_account_id": "ACCOUNT_123456",
  "status": "processing",
  "attempt_count": 1,
  "last_attempt_at": "2024-01-15T11:01:00Z",
  "error_message": "",
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:01:00Z",
  "completed_at": null
}
```

### List Payouts

```
GET /payouts/
```

**Query Parameters**:
- `merchant` (UUID): Filter by merchant ID
- `page` (integer): Page number (default: 1)

**Response** (200 OK):
```json
{
  "count": 10,
  "next": "http://localhost:8000/api/v1/payouts/?page=2",
  "previous": null,
  "results": [
    {
      "id": "750e8400-e29b-41d4-a716-446655440002",
      "merchant": "550e8400-e29b-41d4-a716-446655440000",
      "amount_paise": 50000,
      "bank_account_id": "ACCOUNT_123456",
      "status": "completed",
      "attempt_count": 1,
      "error_message": "",
      "created_at": "2024-01-15T11:00:00Z",
      "completed_at": "2024-01-15T11:05:00Z"
    }
  ]
}
```

### Get Payout Status

```
GET /payouts/{id}/status/
```

**Response** (200 OK):
```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "status": "completed",
  "amount_paise": 50000,
  "created_at": "2024-01-15T11:00:00Z",
  "completed_at": "2024-01-15T11:05:00Z",
  "error_message": ""
}
```

## Payout Status Values

- `pending`: Waiting to be processed
- `processing`: Being processed by the bank settlement simulator
- `completed`: Successfully completed
- `failed`: Failed (funds returned to merchant balance)

## Error Responses

All errors follow this format:

```json
{
  "error": "Human-readable error message",
  "detail": "Additional details (if applicable)"
}
```

## Idempotency

### How to Use

1. Generate a UUID for your request
2. Include it in the `Idempotency-Key` header
3. If the same key is used within 24 hours, you get the same response
4. If 24 hours pass, the key expires and a new request creates a new payout

### Example Flow

**Request 1**:
```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "550e8400-e29b-41d4-a716-446655440000",
    "amount_paise": 50000,
    "bank_account_id": "ACCOUNT_123456"
  }'
```

**Response** (201 Created):
```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  ...
}
```

**Request 2** (Same key, within 24 hours):
```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "550e8400-e29b-41d4-a716-446655440000",
    "amount_paise": 50000,
    "bank_account_id": "ACCOUNT_123456"
  }'
```

**Response** (200 OK - Same payout):
```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "status": "pending",  // May have changed
  ...
}
```

## Rate Limiting

Not currently implemented. Implement in production using:
- `django-ratelimit`
- `djangorestframework-throttling`
- Nginx rate limiting

## Examples

### Create a Payout with Python

```python
import requests
import uuid

MERCHANT_ID = "550e8400-e29b-41d4-a716-446655440000"
IDEMPOTENCY_KEY = str(uuid.uuid4())

response = requests.post(
    'http://localhost:8000/api/v1/payouts/',
    json={
        'merchant_id': MERCHANT_ID,
        'amount_paise': 50000,
        'bank_account_id': 'ACCOUNT_123456'
    },
    headers={
        'Idempotency-Key': IDEMPOTENCY_KEY
    }
)

print(response.status_code)
print(response.json())
```

### Create a Payout with cURL

```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "550e8400-e29b-41d4-a716-446655440000",
    "amount_paise": 50000,
    "bank_account_id": "ACCOUNT_123456"
  }'
```

### Check Merchant Balance

```bash
curl http://localhost:8000/api/v1/merchants/550e8400-e29b-41d4-a716-446655440000/balance/
```

## WebSocket Updates (Future Enhancement)

Real-time status updates can be implemented using Django Channels:
```
WS /ws/payouts/{payout_id}/
```

Clients subscribe to receive `status_changed` events.
