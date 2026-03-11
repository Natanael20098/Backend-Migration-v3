# client-crm-service

FastAPI service for the Client/CRM and Brokerage/Agent domain. Wave 2A of the HomeLend Pro
Java-to-Python migration. Implements the same external API contract as the Java
`ClientController` and `AgentController`.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| GET | `/api/clients` | JWT | List clients (filters: `clientType`, `assignedAgentId`) |
| GET | `/api/clients/{id}` | JWT | Get client by ID |
| POST | `/api/clients` | JWT | Create client |
| PUT | `/api/clients/{id}` | JWT | Update client |
| DELETE | `/api/clients/{id}` | JWT | Delete client |
| GET | `/api/clients/{id}/documents` | JWT | List client documents |
| POST | `/api/clients/{id}/documents` | JWT | Upload client document |
| GET | `/api/agents` | JWT | List agents (filters: `brokerageId`, `isActive`) |
| GET | `/api/agents/{id}` | JWT | Get agent by ID |
| POST | `/api/agents` | JWT | Create agent |
| PUT | `/api/agents/{id}` | JWT | Update agent |
| DELETE | `/api/agents/{id}` | JWT | Delete agent |
| GET | `/api/agents/{id}/licenses` | JWT | List agent licenses |
| POST | `/api/agents/{id}/licenses` | JWT | Add agent license |
| GET | `/api/agents/{id}/commissions` | JWT | List agent commissions |
| POST | `/api/agents/{id}/commissions` | JWT | Record agent commission |
| GET | `/api/brokerages` | JWT | List brokerages |
| GET | `/api/brokerages/{id}` | JWT | Get brokerage by ID |
| POST | `/api/brokerages` | JWT | Create brokerage |
| PUT | `/api/brokerages/{id}` | JWT | Update brokerage |
| DELETE | `/api/brokerages/{id}` | JWT | Delete brokerage |
| GET | `/api/leads` | JWT | List leads (filters: `status`, `assignedAgentId`, `clientId`) |
| GET | `/api/leads/{id}` | JWT | Get lead by ID |
| POST | `/api/leads` | JWT | Create lead |
| PUT | `/api/leads/{id}` | JWT | Update lead |
| DELETE | `/api/leads/{id}` | JWT | Delete lead |
| GET | `/api/showings` | JWT | List showings (filters: `status`, `clientId`, `agentId`, `listingId`) |
| GET | `/api/showings/{id}` | JWT | Get showing by ID |
| POST | `/api/showings` | JWT | Schedule showing |
| PUT | `/api/showings/{id}` | JWT | Update showing |
| DELETE | `/api/showings/{id}` | JWT | Delete showing |
| GET | `/api/offers` | JWT | List offers (filters: `status`, `listingId`, `buyerClientId`) |
| GET | `/api/offers/{id}` | JWT | Get offer by ID |
| POST | `/api/offers` | JWT | Submit offer |
| PUT | `/api/offers/{id}` | JWT | Update offer |
| DELETE | `/api/offers/{id}` | JWT | Delete offer |
| GET | `/api/offers/{id}/counter-offers` | JWT | List counter-offers |
| POST | `/api/offers/{id}/counter-offers` | JWT | Submit counter-offer |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://` URL (Supabase transaction pooler, port 6543) |
| `JWT_SECRET` | Yes | Must match Java monolith and all FastAPI services |
| `JWT_EXPIRATION_MS` | No | Token TTL in ms (default: 86400000) |
| `FRONTEND_URL` | No | CORS allowed origin (default: `http://localhost:3000`) |

## Running Locally

```bash
# From the services/ directory:
cd services
pip install -r client-crm-service/requirements.txt
DATABASE_URL=... JWT_SECRET=... uvicorn app.main:app --port 8005 --reload
```

## Running with Docker Compose

```bash
# From the project root:
docker compose up client-crm-service
```

## Smoke Tests

```bash
export TOKEN="<jwt-from-login>"

# Health check
curl -I http://localhost:8005/health

# List clients
curl -H "Authorization: Bearer $TOKEN" http://localhost/api/clients

# Create a client
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"firstName":"Jane","lastName":"Doe","email":"jane@example.com","clientType":"BUYER"}' \
  http://localhost/api/clients

# List agents
curl -H "Authorization: Bearer $TOKEN" http://localhost/api/agents

# Invalid token — should return 401
curl -H "Authorization: Bearer invalid-token" http://localhost/api/clients
```

## Migration Wave

**Wave 2A** — See `doc/remaining-domains-inventory.md` and `doc/cutover-records/client-crm-service-cutover.md`.

**Tables owned (post-cutover):**
`clients`, `client_documents`, `leads`, `showings`, `offers`, `counter_offers`,
`agents`, `agent_licenses`, `brokerages`, `commissions`

**Java classes to retire after cutover:**
- `com.zcloud.platform.controller.ClientController`
- `com.zcloud.platform.controller.AgentController`
- `com.zcloud.platform.service.MasterService` (client/agent portions)

## Security Note

SSN data (`ssn_encrypted`) is stored in the `clients` table from the Java era.
This service does NOT expose `ssn_encrypted` in any API response. A dedicated
security review for SSN handling is required before this service is considered
fully production-hardened. See `doc/remaining-domains-inventory.md` §3.2.
