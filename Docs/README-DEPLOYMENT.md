# FinTech SaaS - Deployment Scripts

## 🚀 Quick Deployment Options

### 1. Auto-Deploy Script (Recommended)
**File:** `scripts/auto-deploy-fintech.sh`

**Features:**
- ✅ Deploys only FinTech project (no other projects affected)
- ✅ Automatic health checks
- ✅ Backup and rollback capability
- ✅ Detailed logging and status reporting
- ✅ Docker image cleanup

**Usage:**
```bash
# Deploy main branch
./scripts/auto-deploy-fintech.sh deploy main

# Deploy develop branch
./scripts/auto-deploy-fintech.sh deploy develop

# Check status
./scripts/auto-deploy-fintech.sh status

# Rollback to last backup
./scripts/auto-deploy-fintech.sh rollback

# Show help
./scripts/auto-deploy-fintech.sh help
```

### 2. Quick Deploy Script
**File:** `scripts/quick-deploy.sh`

**Features:**
- ⚡ Fast deployment
- 🎯 Targets only FinTech containers
- 🔄 Auto-reloads nginx gateway

**Usage:**
```bash
# Deploy main branch (default)
./scripts/quick-deploy.sh

# Deploy specific branch
./scripts/quick-deploy.sh develop
```

## 🖥️ Server Details

- **Server IP:** 134.195.138.56
- **User:** root
- **Project Directory:** `/var/www/airco-fintech/`
- **Live URL:** https://insights.theairco.ai
- **Health Check:** https://insights.theairco.ai/health

## 🐳 Container Information

### FinTech Containers Only:
- `fintech_backend` - FastAPI backend (Port 8000)
- `fintech_frontend` - Next.js frontend (Port 3000)

### Shared Gateway (Not affected):
- `nginx-gateway` - Shared nginx proxy (Ports 80, 443)

## 📋 Deployment Process

### What the scripts do:
1. **Pull latest code** from Git repository
2. **Stop only FinTech containers** (fintech_backend, fintech_frontend)
3. **Rebuild Docker images** with no cache
4. **Start containers** in detached mode
5. **Run health checks** on both services
6. **Reload nginx gateway** (safe shared operation)
7. **Clean up unused images**

### What they DON'T affect:
- ❌ Other project containers
- ❌ Shared nginx configuration
- ❌ SSL certificates
- ❌ Database data
- ❌ Other applications on server

## 🔧 Safety Features

### Auto-Deploy Script:
- **Pre-deployment checks** (server connectivity, directory exists)
- **Automatic backups** of docker-compose.yml
- **Health validation** before/after deployment
- **Rollback capability** if something goes wrong
- **Detailed logging** with colored output

### Quick Deploy Script:
- **Minimal operations** for speed
- **Error handling** with set -e
- **Status reporting** after deployment

## 📊 Health Checks

### Backend Health:
```bash
curl https://insights.theairco.ai/health
# Expected: {"status":"ok"}
```

### Frontend Health:
```bash
curl https://insights.theairco.ai
# Expected: HTML response with Next.js app
```

## 🔄 Rollback Process

If deployment fails:
```bash
./scripts/auto-deploy-fintech.sh rollback
```

This will:
1. Stop current containers
2. Restore last docker-compose backup
3. Restart with previous configuration

## 🚨 Troubleshooting

### Common Issues:
1. **SSH Connection Failed**
   - Check server IP and SSH key
   - Verify internet connectivity

2. **Container Failed to Start**
   - Check logs: `docker logs fintech_backend`
   - Verify docker-compose file syntax

3. **Health Check Failed**
   - Wait longer for services to start
   - Check port conflicts
   - Verify environment variables

### Manual Commands:
```bash
# SSH to server
ssh root@134.195.138.56

# Navigate to project
cd /var/www/airco-fintech

# Check container status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker logs fintech_backend
docker logs fintech_frontend

# Restart containers
docker-compose -f docker-compose.prod.yml restart
```

## 📝 Notes

- Scripts are designed to be **project-isolated**
- **No impact** on other projects sharing the nginx gateway
- **Automatic cleanup** of old Docker images
- **Git-based** deployment with version control
- **Health monitoring** with automatic validation

## 🎯 Best Practices

1. **Test on develop branch** first
2. **Check status** before deploying
3. **Monitor health** after deployment
4. **Keep backups** for quick rollback
5. **Use auto-deploy script** for production deployments
6. **Use quick-deploy script** for rapid iterations
