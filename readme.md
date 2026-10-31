# MediParse API

A multi-tenant Healthcare Document Intelligence API that enables healthcare organizations to upload medical documents (PDFs/images), extract structured data using Claude AI, and expose it via a secure role-gated REST API with full audit logging.

---

## Tech Stack

- **Backend:** Django 4.2 + Django REST Framework
- **Auth:** JWT via `djangorestframework-simplejwt`
- **Database:** PostgreSQL
- **Cache/Queue:** Redis + Celery
- **AI:** Anthropic Claude API
- **Storage:** AWS S3
- **Infra:** AWS ECS Fargate + RDS
- **Docs:** drf-spectacular (Swagger UI)
- **Containerization:** Docker + Docker Compose

---

## Project Structure

```
mediparse/
├── apps/
│ ├── accounts/ # User, Organization, JWT auth
│ ├── documents/ # Document upload, S3
│ ├── extraction/ # Claude integration, ExtractedRecord
│ ├── patients/ # Patient CRUD
│ └── audit/ # Audit log middleware
├── common/ # Shared permissions, pagination, exceptions
├── config/
│ ├── settings/
│ │ ├── base.py
│ │ ├── dev.py
│ │ └── prod.py
│ └── urls.py
├── requirements/
│ ├── base.txt
│ ├── dev.txt
│ └── prod.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Local Development Setup

### Prerequisites
- Docker + Docker Compose
- Python 3.12+

### Steps

1. Clone the repository
```bash
git clone https://github.com/your-username/mediparse.git
cd mediparse
```

2. Create your `.env` file
```bash
cp .env.example .env
```

3. Generate a secret key and paste it into `.env`
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

4. Start the containers
```bash
docker-compose up --build
```

5. Run migrations
```bash
docker-compose exec api python manage.py migrate
```

6. Visit `http://localhost:8000/api/docs/` for Swagger UI

---

## API Endpoints

### Auth
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/auth/register/` | Public | Register user + organization |
| POST | `/api/auth/login/` | Public | Login, returns JWT tokens |
| POST | `/api/auth/refresh/` | Public | Refresh access token |
| GET | `/api/auth/me/` | Authenticated | Get current user details |

---

## Roles & Permissions

| Role | Permissions |
|------|-------------|
| Admin | Full access — manage users, all CRUD |
| Doctor | Upload documents, view extracted data |
| Nurse | View documents and extracted data |
| Viewer | Read-only access |

Multi-tenancy is enforced at the object level — users can only access data within their own organization.

---

## Build Status

| Sprint | Description | Status |
|--------|-------------|--------|
| Sprint 1 | Project scaffold, Docker, settings split, User/Org models, JWT auth, RBAC | ✅ Complete |
| Sprint 2 | S3 integration, document upload, Patient CRUD, status tracking | 🔜 Upcoming |
| Sprint 3 | Claude integration, extraction prompt, ExtractedRecord, Celery async | 🔜 Upcoming |
| Sprint 4 | Audit log, rate limiting, Swagger docs, pytest tests | 🔜 Upcoming |
| Sprint 5 | Dockerfile prod, ECS Fargate deploy, RDS, GitHub Actions CI/CD | 🔜 Upcoming |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | True for dev, False for prod |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `AWS_ACCESS_KEY_ID` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_S3_BUCKET_NAME` | S3 bucket for document storage |
| `ANTHROPIC_API_KEY` | Claude API key |