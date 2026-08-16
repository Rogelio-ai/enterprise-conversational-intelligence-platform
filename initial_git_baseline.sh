# ============================================================
# PRYECIP — INITIAL GIT BASELINE
# ============================================================

cd /ruta/al/proyecto/pryecip


# 1. Inicializar Git
git init


# 2. Establecer main como rama principal
git branch -M main


# 3. Verificar estado inicial
git status


# 4. Crear .gitignore inicial
cat > .gitignore <<'EOF'
# ============================================================
# Python
# ============================================================
__pycache__/
*.py[cod]
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/
env/

# ============================================================
# Node / Frontend
# ============================================================
node_modules/
dist/
build/
.vite/
coverage/

# ============================================================
# Environment / Secrets
# ============================================================
.env
.env.*
!.env.example

*.pem
*.key
*.crt
*.p12
*.pfx

# ============================================================
# IDE / Editor
# ============================================================
.vscode/*
!.vscode/extensions.json
!.vscode/settings.example.json

.idea/

# ============================================================
# OS
# ============================================================
.DS_Store
Thumbs.db

# ============================================================
# Logs / Runtime
# ============================================================
*.log
logs/
tmp/
temp/
*.pid

# ============================================================
# Docker / Local persistent data
# ============================================================
docker-data/
data/mysql/
data/redis/
data/minio/

# ============================================================
# Backup / Temporary
# ============================================================
*.bak
*.backup
*.swp
*.swo
*~

# ============================================================
# Generated files
# ============================================================
generated/
artifacts/
EOF


# 5. Crear .env.example si aún no existe
touch .env.example


# 6. Revisar qué se va a versionar
git status


# 7. Agregar baseline documental y estructura actual
git add .


# 8. Verificar exactamente lo que entrará al commit
git status


# 9. Crear primer commit oficial
git commit -m "chore(repository): establish initial ECIP project baseline"


# 10. Crear tag de baseline documental inicial
git tag -a restaurant-domain-model-v1.0.0 \
  -m "Restaurant Domain Model v1.0.0 baseline"


# 11. Crear tag del MVP scope aprobado
git tag -a restaurant-mvp-scope-v1.0.0 \
  -m "Restaurant MVP Production Scope v1.0.0 baseline"


# 12. Crear tag del Implementation Plan
git tag -a restaurant-implementation-plan-v1.0.0 \
  -m "Restaurant Implementation Plan v1.0.0 baseline"


# 13. Verificar historial y tags
git log --oneline --decorate -5

git tag --list
