# FinTech SaaS — Utho Deployment Architecture
=================================================================================================

## Overview
Airco Insights (FinTech SaaS) is deployed on Utho (134.195.138.56) as a multi-container Docker application behind a shared nginx gateway. The system processes bank statement PDFs and returns categorized Excel reports.

---

## 🏗️ Server & Network Layout

### Host Server Details
- **IP**: 134.195.138.56
- **OS**: Linux (Docker host)
- **Project Directory**: `/var/www/airco-fintech/`
- **SSL**: Cloudflare Full Strict (origin certificates in `/ssl/`)

### Container Network
- **Docker Network**: `airco-fintech_default` (bridge network)
- **Subnet**: 172.19.0.0/16
- **Gateway**: Shared `nginx-gateway` container handles public traffic

---

## 🐳 Docker Containers

### 1. FinTech Backend Container
```yaml
Container Name: fintech_backend
Image: airco-fintech_backend:latest (built locally)
Port: 8000 (internal only)
Health: /health endpoint
Purpose: FastAPI backend for PDF processing
```

**Key Components:**
- FastAPI application (`uvicorn app.main:app --host 0.0.0.0 --port 8000`)
- SBI bank statement parser/processor
- PDF text extraction with pdfplumber
- Excel report generation with xlsxwriter
- File handling in `/app/tmp` (volume: `backend_tmp`)

**Important Files:**
- `/app/main.py` - FastAPI app entry point
- `/app/routers/upload.py` - `/process` endpoint
- `/app/services/banks/sbi/` - SBI-specific processing
- `/app/services/pipeline_orchestrator.py` - Bank routing logic

### 2. FinTech Frontend Container
```yaml
Container Name: fintech_frontend
Image: airco-fintech_frontend:latest (built locally)
Port: 3000 (internal only)
Purpose: Next.js frontend application
```

**Key Components:**
- Next.js 14 production build
- API routes: `/api/upload`, `/api/download/[filename]`, `/api/check-pdf`
- Static assets served from `/_next/static/`
- Backend proxy via `BACKEND_URL` environment variable

**Important Files:**
- `/app/page.tsx` - Main upload interface
- `/app/components/` - React components (UploadStep, ResultStep, etc.)
- `/app/api/` - API routes that proxy to backend

### 3. Shared Nginx Gateway (External)
```yaml
Container Name: nginx-gateway
Image: nginx:alpine
Ports: 80, 443 (public)
Purpose: Reverse proxy for all applications on server
```

**Gateway Configuration:**
- Config file: `/etc/nginx/conf.d/fintech.conf`
- Handles: `insights.theairco.ai` and `test.theairco.ai`
- SSL termination with Cloudflare origin certificates
- Upstreams: `fintech_frontend:3000`, `fintech_backend:8000`

---

## 🌐 Network Flow & Ports

### Public Access (via Cloudflare → nginx-gateway)
```
https://insights.theairco.ai → nginx-gateway:443 → fintech_frontend:3000
https://insights.theairco.ai/health → nginx-gateway:443 → fintech_backend:8000/health
```

### Internal Container Communication
```
fintech_frontend → http://backend:8000 (via Docker internal DNS)
nginx-gateway → fintech_frontend:3000, fintech_backend:8000
```

### Port Summary
| Service | Internal Port | Public Access | Notes |
|---------|---------------|---------------|-------|
| nginx-gateway | 80, 443 | Yes (Cloudflare) | Public entry point |
| fintech_backend | 8000 | No (internal only) | FastAPI backend |
| fintech_frontend | 3000 | No (internal only) | Next.js frontend |

---

## 📁 Critical File Locations

### On Utho Server (`/var/www/airco-fintech/`)
```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── routers/
│   │   └── upload.py       # Upload endpoint with SBI fixes
│   └── services/
│       ├── pipeline_orchestrator.py
│       └── banks/
│           └── sbi/
│               ├── parser.py              # SBI PDF parser (fixed)
│               ├── processor.py           # SBI processor (zero-transaction guard)
│               ├── structure_validator.py  # SBI structure validator (DD/MM/YYYY)
│               └── report_generator.py     # Excel generator
├── Dockerfile
└── requirements.txt

frontend/
├── app/
│   ├── page.tsx            # Main upload interface
│   ├── components/
│   │   ├── UploadStep.tsx  # File upload component
│   │   ├── ResultStep.tsx  # Results display (shows "Categorization Complete")
│   │   └── DownloadButtons.tsx
│   └── api/
│       ├── upload/route.ts  # Proxies to backend /process
│       └── download/[filename]/route.ts  # Download proxy
├── Dockerfile
├── package.json
└── next.config.js

nginx/
└── nginx.conf              # NOT USED (gateway handles routing)

ssl/
├── origin.pem              # SSL certificate
└── origin-key.pem          # SSL private key

docker-compose.prod.yml     # Production compose file
```

### In Shared Gateway (`nginx-gateway` container)
```
/etc/nginx/conf.d/fintech.conf    # FinTech routing rules
/etc/nginx/ssl/                    # SSL certificates (mounted from host)
/var/log/nginx/fintech-access.log  # Access logs
/var/log/nginx/fintech-error.log   # Error logs
```

---

## 🔧 Configuration Files

### 1. Docker Compose (`docker-compose.prod.yml`)
```yaml
version: '3.9'
services:
  backend:
    image: airco-fintech_backend:latest  # Built locally, not pulled
    container_name: fintech_backend
    restart: always
    expose:
      - "8000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
      SUPABASE_URL: ${SUPABASE_URL}
      TEMP_DIR: /app/tmp
    volumes:
      - backend_tmp:/app/tmp
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

  frontend:
    image: airco-fintech_frontend:latest  # Built locally, not pulled
    container_name: fintech_frontend
    restart: always
    expose:
      - "3000"
    environment:
      BACKEND_URL: http://backend:8000
      NEXT_PUBLIC_API_URL: https://test.theairco.ai

volumes:
  backend_tmp:
    driver: local
```

### 2. Nginx Gateway (`/etc/nginx/conf.d/fintech.conf`)
```nginx
# Upstreams
upstream fintech_frontend {
    server fintech_frontend:3000;
    keepalive 16;
}

upstream fintech_backend {
    server fintech_backend:8000;
    keepalive 8;
}

# HTTPS Server
server {
    listen 443 ssl;
    server_name insights.theairco.ai test.theairco.ai;
    
    # SSL certificates
    ssl_certificate     /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin-key.pem;
    
    # Backend health check
    location = /health {
        proxy_pass http://fintech_backend/health;
    }
    
    # All traffic → Next.js frontend
    location / {
        proxy_pass http://fintech_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
}
```

---

## 🚀 Application Flow

### 1. User Upload Flow
```
1. User uploads PDF via https://insights.theairco.ai
2. Cloudflare → nginx-gateway → fintech_frontend:3000
3. Frontend POSTs to /api/upload (Next.js API route)
4. /api/upload proxies to backend http://backend:8000/process
5. Backend processes PDF with SBI parser/processor
6. Backend returns JSON with download URL or error
7. Frontend displays results or error message
```

### 2. Download Flow
```
1. User clicks download → /api/download/[filename]
2. Frontend proxies to backend /download/[filename]
3. Backend serves Excel file from /app/tmp
4. nginx-gateway streams file to user
```

### 3. Error Handling Flow
```
1. SBI parser fails → HTTP 400 from backend
2. Frontend API route translates to friendly message
3. UI shows error instead of "Categorization Complete"
4. No bogus .htm download (fixed in latest deployment)
```

---

## 🔍 SBI Processing Details

### SBI Parser Flow
```
1. PDF received via upload endpoint
2. Structure validator checks for SBI markers
3. Parser tries text extraction first (internet banking PDFs)
4. Falls back to coordinate-based parsing if needed
5. Extracts transactions with DD/MM/YYYY date format
6. Validates and categorizes transactions
7. Generates Excel report with 8 sheets
8. Returns download URL or error
```

### Key SBI Fixes Applied
- **Parser**: Text-first parsing for SBI internet banking PDFs
- **Structure Validator**: Accepts DD/MM/YYYY format and SBI markers
- **Processor**: Hard failure on zero transactions
- **Upload Router**: HTTP 400 on parse failure
- **Error Messages**: Clear feedback instead of fake success

---

## 📊 Monitoring & Logs

### Health Checks
- **Backend**: `GET /health` returns `{"status":"ok"}`
- **Frontend**: Serves HTML at root path
- **Gateway**: nginx health status via container status

### Log Locations
```
Backend logs: docker logs fintech_backend
Frontend logs: docker logs fintech_frontend
Gateway access: /var/log/nginx/fintech-access.log (in nginx-gateway container)
Gateway errors: /var/log/nginx/fintech-error.log (in nginx-gateway container)
```

### Monitoring Commands
```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# View backend logs
docker logs fintech_backend --tail=50

# View gateway errors
docker exec nginx-gateway tail -n 50 /var/log/nginx/fintech-error.log

# Test health endpoints
curl https://insights.theairco.ai/health
```

---

## 🔄 Deployment Process

### 1. Code Updates
```bash
# Copy updated files to server
scp backend/app/services/banks/sbi/* root@134.195.138.56:/var/www/airco-fintech/backend/app/services/banks/sbi/

# Stop containers
docker-compose -f docker-compose.prod.yml down

# Rebuild with no cache
docker-compose -f docker-compose.prod.yml build --no-cache

# Start containers
docker-compose -f docker-compose.prod.yml up -d

# Reload nginx gateway (critical!)
docker exec nginx-gateway nginx -s reload
```

### 2. Common Issues & Fixes
- **502 Bad Gateway**: nginx-gateway needs reload after container rebuild
- **Stale Code**: Must rebuild containers (images are built locally)
- **Permission Issues**: Check file permissions in `/var/www/airco-fintech/`
- **SSL Issues**: Verify certificates in `/ssl/` and gateway config

---

## 🛡️ Security Considerations

### Network Security
- All containers on internal Docker network
- Only nginx-gateway exposed to internet
- Backend/frontend not directly accessible
- Cloudflare provides DDoS protection

### File Security
- Temporary files in `/app/tmp` (volume)
- PDFs processed and deleted automatically
- No persistent storage of user files
- SSL termination at gateway

### Environment Variables
- Database credentials in environment variables
- API keys for external services
- No hardcoded secrets in code

---

## 📈 Performance Considerations

### Scaling
- Horizontal scaling possible via container replication
- nginx-gateway can load balance multiple backend/frontend instances
- File processing is CPU-intensive (consider resource limits)

### Caching
- nginx-gateway can cache static assets
- Next.js builds optimized static files
- No database caching (stateless design)

### Resource Limits
- Backend: PDF processing memory usage
- Frontend: Node.js memory for Next.js
- Gateway: Connection limits and timeouts

---

## 🚨 Troubleshooting Guide

### Common Issues
1. **502 Bad Gateway**: Reload nginx-gateway after container changes
2. **Upload Fails**: Check backend logs for parser errors
3. **Download Returns HTML**: Backend likely returned error; check logs
4. **SBI PDFs Not Parsing**: Verify SBI parser updates are deployed
5. **SSL Issues**: Check certificate paths in gateway config

### Debug Commands
```bash
# Check container connectivity
docker exec nginx-gateway getent hosts fintech_backend

# Test internal endpoints
docker exec nginx-gateway wget -qO- http://fintech_backend:8000/health

# View real-time logs
docker logs -f fintech_backend

# Check nginx configuration
docker exec nginx-gateway nginx -t

```

🌐 Project Deployment Location
Primary Production Server:
Server: Utho Cloud
IP Address: 134.195.138.56
User: root
Deployment Directory: /var/www/airco-fintech/
Live URLs:
FinTech Application: https://insights.theairco.ai
Health Check: https://insights.theairco.ai/health
API Endpoints: https://insights.theairco.ai/api/
Container Status:
fintech_backend    - Running (Port 8000)
fintech_frontend   - Running (Port 3000)
nginx-gateway      - Running (Ports 80, 443)
Infrastructure Details:
Docker Containers: Built from local source code
Nginx Gateway: Shared with other projects (Airco Secure)
SSL Certificates: Cloudflare Full Strict origin certs
Database: Supabase integration
SBI Integration Status:
✅ SBI Parser: Deployed and ready
✅ Frontend Option: SBI available in bank dropdown
✅ Backend Processing: Full SBI PDF processing pipeline
✅ All 27 Files: Successfully deployed
Access Credentials:
SSH Access: ssh root@134.195.138.56
Web Access: https://insights.theairco.ai
Admin Panel: Through web interface

lets deploy full project 1st on github 




---

## 📝 Summary

The FinTech SaaS application runs on Utho as a containerized Docker deployment behind a shared nginx gateway. The system processes bank statement PDFs (with specialized SBI parsing) and serves categorized Excel reports through a Next.js frontend. Key architectural points:

- **Microservices**: Separate backend (FastAPI) and frontend (Next.js) containers
- **Gateway Pattern**: Shared nginx handles SSL and routing
- **Local Builds**: Images built on server, not pulled from registry
- **Stateless Design**: No persistent data storage
- **Security**: Internal networking, SSL termination, Cloudflare protection

The recent SBI fixes have been deployed and the gateway has been reloaded to resolve the 502 issue. The system should now properly handle SBI PDFs and provide clear error messages instead of fake success states.
