# MediParse API

A multi-tenant Healthcare Document Intelligence API that enables healthcare organizations to upload medical documents (PDFs/images), extract structured data using Claude AI, and expose it via a secure role-gated REST API with full audit logging.

---

## Tech Stack

- **Backend:** Django 4.2 + Django REST Framework
- **Auth:** JWT via `djangorestframework-simplejwt`
- **Database:** PostgreSQL
- **Cache/Queue:** Redis + Celery
- **AI:** Google Gemini API (`gemini-3.5-flash-lite`) via `google-genai`, structured JSON output
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
git clone https://github.com/Biswajit-Rakshit/MediParse.git
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

### Patients
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/patients/` | Nurse+ | List all patients in org |
| POST | `/api/patients/` | Doctor+ | Create a patient |
| GET | `/api/patients/<id>/` | Nurse+ | Retrieve a patient |
| PATCH | `/api/patients/<id>/` | Doctor+ | Update a patient |

### Documents
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/documents/` | Nurse+ | List all documents in org |
| POST | `/api/documents/` | Doctor+ | Upload a document to S3 |
| GET | `/api/documents/<id>/` | Nurse+ | Retrieve a document + presigned URL |

### Extractions
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/documents/<id>/extraction/` | Nurse+ | Extracted data for one document |
| GET | `/api/extractions/` | Nurse+ | List extracted records in org |

### Query parameters
| Endpoint | Parameters |
|----------|------------|
| `/api/patients/` | `search`, `gender`, `page`, `page_size` |
| `/api/documents/` | `status`, `file_type`, `patient`, `page`, `page_size` |
| `/api/extractions/` | `search`, `min_confidence`, `page`, `page_size` |

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
| Sprint 2 | S3 integration, document upload, Patient CRUD, status tracking | ✅ Complete |
| Sprint 3 | Gemini extraction, ExtractedRecord, Celery async pipeline, pagination + filtering | ✅ Complete |
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
| `AWS_S3_REGION` | S3 bucket region |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Model ID (default `gemini-3.5-flash-lite`) |

## Data Safety
This project is a portfolio demonstration. Use only synthetic documents. The free
Gemini API tier may use submitted content to improve Google products, so real patient
data must never be uploaded.