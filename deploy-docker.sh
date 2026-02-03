#!/bin/bash
###
# OpenVPN Manager - Ubuntu 一键 Docker 部署脚本
# 适配 angristan/openvpn-install 脚本
# 系统要求: Ubuntu 22.04+ 已安装 OpenVPN
###

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否为 root 用户
if [[ $EUID -ne 0 ]]; then
   log_error "请使用 root 或 sudo 运行此脚本"
   echo "用法: sudo bash deploy-docker.sh"
   exit 1
fi

clear
echo "=========================================="
echo "   OpenVPN Manager Docker 一键部署"
echo "   适配 angristan 脚本 + Ubuntu 22.04"
echo "=========================================="
echo ""

# ==================== 步骤 1: 检查 OpenVPN ====================
log_step "1/8 检查 OpenVPN 服务..."

OPENVPN_SERVICE=""
MANAGEMENT_TYPE=""
MANAGEMENT_SOCKET=""
MANAGEMENT_HOST=""
MANAGEMENT_PORT=""
EASYRSA_PATH=""
SERVER_CONF=""

# 检测服务名
if systemctl list-units --full --all | grep -q "openvpn-server@server.service"; then
    OPENVPN_SERVICE="openvpn-server@server"
    log_info "✓ 检测到 angristan 脚本安装 (openvpn-server@server)"
elif systemctl list-units --full --all | grep -q "openvpn@server.service"; then
    OPENVPN_SERVICE="openvpn@server"
    log_info "✓ 检测到传统安装 (openvpn@server)"
else
    log_error "未检测到 OpenVPN 服务"
    echo ""
    echo "请先使用 angristan 脚本安装 OpenVPN："
    echo "  wget https://raw.githubusercontent.com/angristan/openvpn-install/master/openvpn-install.sh"
    echo "  chmod +x openvpn-install.sh"
    echo "  sudo ./openvpn-install.sh"
    exit 1
fi

# 检查服务状态
if ! systemctl is-active --quiet "$OPENVPN_SERVICE"; then
    log_warn "OpenVPN 服务未运行，尝试启动..."
    systemctl start "$OPENVPN_SERVICE"
    sleep 2
fi

if systemctl is-active --quiet "$OPENVPN_SERVICE"; then
    log_info "✓ OpenVPN 服务运行正常"
else
    log_error "OpenVPN 服务启动失败"
    systemctl status "$OPENVPN_SERVICE"
    exit 1
fi

# ==================== 步骤 2: 检测配置文件 ====================
log_step "2/8 检测 OpenVPN 配置..."

if [[ -f "/etc/openvpn/server/server.conf" ]]; then
    SERVER_CONF="/etc/openvpn/server/server.conf"
    EASYRSA_PATH="/etc/openvpn/server/easy-rsa"
    log_info "✓ 配置文件: $SERVER_CONF"
elif [[ -f "/etc/openvpn/server.conf" ]]; then
    SERVER_CONF="/etc/openvpn/server.conf"
    EASYRSA_PATH="/etc/openvpn/easy-rsa"
    log_info "✓ 配置文件: $SERVER_CONF"
else
    log_error "未找到 OpenVPN 配置文件"
    exit 1
fi

# 检测 Management 接口类型
if grep -q "management.*\.sock.*unix" "$SERVER_CONF"; then
    MANAGEMENT_TYPE="unix"
    MANAGEMENT_SOCKET=$(grep "management" "$SERVER_CONF" | awk '{print $2}')
    log_info "✓ Management 接口: Unix Socket"
    log_info "  Socket 路径: $MANAGEMENT_SOCKET"
elif grep -q "^management" "$SERVER_CONF"; then
    MANAGEMENT_TYPE="tcp"
    MANAGEMENT_HOST=$(grep "^management" "$SERVER_CONF" | awk '{print $2}')
    MANAGEMENT_PORT=$(grep "^management" "$SERVER_CONF" | awk '{print $3}')
    log_info "✓ Management 接口: TCP Socket"
    log_info "  地址: $MANAGEMENT_HOST:$MANAGEMENT_PORT"
else
    log_error "未检测到 Management 接口配置"
    echo ""
    echo "请在 $SERVER_CONF 中添加以下任一配置："
    echo "  方式1 (推荐): management /var/run/openvpn-server/server.sock unix"
    echo "  方式2:        management 127.0.0.1 7505"
    exit 1
fi

# ==================== 步骤 3: 检查必要目录 ====================
log_step "3/8 检查并创建必要目录..."

REQUIRED_DIRS=(
    "/etc/openvpn/ccd"
    "/etc/openvpn/client-configs"
    "/var/log/openvpn"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        chmod 755 "$dir"
        log_info "✓ 创建目录: $dir"
    else
        log_info "✓ 目录已存在: $dir"
    fi
done

# 检查 Socket 目录权限
if [[ "$MANAGEMENT_TYPE" == "unix" ]]; then
    SOCKET_DIR=$(dirname "$MANAGEMENT_SOCKET")
    if [[ -d "$SOCKET_DIR" ]]; then
        chmod 755 "$SOCKET_DIR"  # 修改权限以便 Docker 容器访问
        log_info "✓ Socket 目录权限已调整: $SOCKET_DIR"
    fi
fi

# ==================== 步骤 4: 安装 Docker ====================
log_step "4/8 检查 Docker 环境..."

if ! command -v docker &> /dev/null; then
    log_warn "Docker 未安装，开始安装..."
    apt-get update
    apt-get install -y ca-certificates curl gnupg lsb-release
    
    # 添加 Docker 官方 GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # 添加 Docker 仓库
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    log_info "✓ Docker 安装完成"
else
    log_info "✓ Docker 已安装"
fi

# 检查 Docker Compose
if docker compose version &> /dev/null; then
    log_info "✓ Docker Compose 已安装 (V2)"
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    log_info "✓ Docker Compose 已安装 (V1)"
    COMPOSE_CMD="docker-compose"
else
    log_warn "Docker Compose 未安装，正在安装..."
    apt-get install -y docker-compose
    COMPOSE_CMD="docker-compose"
fi

# 启动 Docker 服务
if ! systemctl is-active --quiet docker; then
    systemctl start docker
    systemctl enable docker
fi
log_info "✓ Docker 服务运行正常"

# ==================== 步骤 5: 获取网络配置 ====================
log_step "5/8 获取网络配置..."

# 获取公网 IP
PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "")
if [[ -z "$PUBLIC_IP" ]]; then
    # 尝试从配置文件中读取
    if grep -q "^remote" "$SERVER_CONF"; then
        PUBLIC_IP=$(grep "^remote" "$SERVER_CONF" | awk '{print $2}' | head -1)
    fi
fi

if [[ -z "$PUBLIC_IP" ]]; then
    log_warn "无法自动获取公网 IP"
    read -p "请手动输入公网 IP: " PUBLIC_IP
fi
log_info "✓ 公网 IP: $PUBLIC_IP"

# 获取 OpenVPN 端口
OPENVPN_PORT=$(grep "^port" "$SERVER_CONF" | awk '{print $2}' || echo "1194")
log_info "✓ OpenVPN 端口: $OPENVPN_PORT"

# 获取协议
OPENVPN_PROTO=$(grep "^proto" "$SERVER_CONF" | awk '{print $2}' || echo "udp")
log_info "✓ OpenVPN 协议: $OPENVPN_PROTO"

# ==================== 步骤 6: 配置管理员密码 ====================
log_step "6/8 配置管理员账户..."

echo ""
read -p "设置管理员用户名 (默认: admin): " ADMIN_USERNAME
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}

read -sp "设置管理员密码 (默认: admin456): " ADMIN_PASSWORD
echo ""
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin456}

# 生成随机 SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)

# ==================== 步骤 7: 生成配置文件 ====================
log_step "7/8 生成配置文件..."

# 备份旧配置
if [[ -f "backend/.env" ]]; then
    cp backend/.env "backend/.env.backup.$(date +%Y%m%d_%H%M%S)"
    log_info "✓ 已备份旧配置"
fi

# 生成 backend/.env
cat > backend/.env <<EOF
# OpenVPN Manager 配置文件
# 自动生成于: $(date '+%Y-%m-%d %H:%M:%S')

# ========== 安全配置 ==========
SECRET_KEY=$SECRET_KEY
DEFAULT_ADMIN_USERNAME=$ADMIN_USERNAME
DEFAULT_ADMIN_PASSWORD=$ADMIN_PASSWORD

# ========== OpenVPN 服务配置 ==========
OPENVPN_SERVICE_NAME=$OPENVPN_SERVICE
PUBLIC_IP=$PUBLIC_IP
PUBLIC_PORT=$OPENVPN_PORT

# ========== 路径配置 ==========
OPENVPN_BASE_PATH=/etc/openvpn
EASYRSA_PATH=$EASYRSA_PATH
CCD_PATH=/etc/openvpn/ccd
OPENVPN_CLIENT_EXPORT_PATH=/etc/openvpn/client-configs
OPENVPN_STATUS_PATH=/var/log/openvpn/status.log
OPENVPN_CRL_PATH=/etc/openvpn/server/crl.pem
SERVER_CONF_PATH=$SERVER_CONF

# ========== TLS 认证配置 (自动检测) ==========
TLS_AUTH_MODE=tls-crypt-v2
TLS_CRYPT_V2_KEY_PATH=/etc/openvpn/server/tls-crypt-v2.key
TLS_CRYPT_KEY_PATH=/etc/openvpn/server/tls-crypt.key
TA_KEY_PATH=/etc/openvpn/server/ta.key

EOF

# Management 接口配置
if [[ "$MANAGEMENT_TYPE" == "unix" ]]; then
    cat >> backend/.env <<EOF
# ========== Management 接口 (Unix Socket) ==========
OPENVPN_MANAGEMENT_SOCKET=$MANAGEMENT_SOCKET

EOF
else
    cat >> backend/.env <<EOF
# ========== Management 接口 (TCP Socket) ==========
OPENVPN_MANAGEMENT_HOST=$MANAGEMENT_HOST
OPENVPN_MANAGEMENT_PORT=$MANAGEMENT_PORT

EOF
fi

# 其他配置
cat >> backend/.env <<EOF
# ========== 应用配置 ==========
DEPLOY_ENV=PROD
LOG_LEVEL=INFO
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ========== CORS 配置 ==========
CORS_ORIGINS=["http://localhost:8080","http://127.0.0.1:8080","http://$PUBLIC_IP:8080"]
EOF

log_info "✓ 配置文件已生成: backend/.env"

# 生成前端 .env 文件（使用公网 IP + 端口）
log_info "✓ 生成前端配置文件..."
cat > frontend/.env <<EOF
# 后端 API 地址（完整 URL）
VITE_API_BASE=http://$PUBLIC_IP:8000/api
EOF
log_info "✓ 前端配置已生成: frontend/.env"

# 更新 docker-compose.yml
log_info "✓ 更新 docker-compose.yml..."

cat > docker-compose.yml <<EOF
# Docker Compose 配置文件
# 注意: version 字段在 Docker Compose V2 中已废弃，可以移除

services:
  # 后端服务
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ovpn-backend
    restart: unless-stopped
    network_mode: host
    privileged: true
    volumes:
      # SQLite 数据库
      - ./backend/data:/app/data
      # OpenVPN 配置目录
      - /etc/openvpn/server:/etc/openvpn/server:ro
      # Easy-RSA 目录 (需要写权限以生成证书)
      - /etc/openvpn/server/easy-rsa:/etc/openvpn/server/easy-rsa
      # 日志 (只读)
      - /var/log/openvpn:/var/log/openvpn:ro
      # 可写目录
      - /etc/openvpn/ccd:/etc/openvpn/ccd
      - /etc/openvpn/client-configs:/etc/openvpn/client-configs
EOF

# 根据 Management 类型添加不同的挂载
if [[ "$MANAGEMENT_TYPE" == "unix" ]]; then
    cat >> docker-compose.yml <<EOF
      # Unix Socket
      - /var/run/openvpn-server:/var/run/openvpn-server
EOF
fi

cat >> docker-compose.yml <<EOF
      # systemd 支持
      - /run/systemd:/run/systemd:ro
      - /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket:ro
    env_file:
      - backend/.env

  # 前端服务
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ovpn-frontend
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      - backend
EOF

log_info "✓ docker-compose.yml 已更新"

# 修复前端 Nginx 配置（使用 localhost 而不是 backend）
log_info "✓ 更新 Nginx 配置..."
cat > frontend/nginx.conf <<'NGINX_EOF'
server {
    listen 80;
    server_name _;
    
    # 前端静态资源
    location /ovpnmanager/ {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /ovpnmanager/index.html;
        index index.html;
    }
    
    # 后端 API 代理（backend 使用 host 网络，所以用 localhost）
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location = / {
        return 301 /ovpnmanager/;
    }
}
NGINX_EOF

# 创建数据目录
mkdir -p backend/data
chmod 755 backend/data

# ==================== 步骤 8: 启动服务 ====================
log_step "8/8 启动 Docker 服务..."

# 停止旧服务
$COMPOSE_CMD down 2>/dev/null || true

# 构建并启动
log_info "正在构建镜像，这可能需要几分钟..."
$COMPOSE_CMD up -d --build

# 等待服务启动
log_info "等待服务启动..."
sleep 5

# 等待容器进入 Up 状态 (最多等待30秒)
log_info "检查容器状态..."
for i in {1..30}; do
    if docker ps | grep -q "ovpn-backend"; then
        BACKEND_STATE=$(docker ps --format "{{.Status}}" --filter "name=ovpn-backend")
        if [[ "$BACKEND_STATE" == Up* ]]; then
            log_info "✓ 后端容器已启动 ($i 秒)"
            break
        fi
    fi
    
    if [[ $i -eq 30 ]]; then
        log_error "后端容器启动超时"
        docker ps -a | grep ovpn
        docker logs ovpn-backend --tail 50
        exit 1
    fi
    
    sleep 1
done

# 再等待几秒让应用完全就绪
sleep 3

# 最终确认
if ! docker ps | grep -q "ovpn-backend.*Up"; then
    log_error "后端容器启动失败"
    docker logs ovpn-backend --tail 50
    exit 1
fi

log_info "✓ 容器启动成功"

# 同步管理员账号（确保密码与配置一致）
log_info "同步管理员账号..."
if ! docker exec ovpn-backend python -c "
from app.db.session import SessionLocal
from app import crud
from app.schemas.user import UserCreate
from app.core.config import get_settings

settings = get_settings()
db = SessionLocal()

# 检查用户是否存在
user = crud.user.get_by_username(db, username=settings.default_admin_username)
if user:
    # 删除旧用户
    db.delete(user)
    db.commit()

# 重新创建管理员（确保密码正确）
crud.user.create(
    db,
    obj_in=UserCreate(
        username=settings.default_admin_username,
        password=settings.default_admin_password,
        email=None,
        is_active=True,
        is_superuser=True
    )
)
db.close()
print('✓ 管理员账号已同步')
" 2>&1 | grep -v "bcrypt"; then
    log_error "管理员账号同步失败"
    exit 1
fi

log_info "✓ 管理员账号同步完成"

# 导入 Easy-RSA 证书到数据库
log_info "正在导入 Easy-RSA 证书到数据库..."
if ! docker exec ovpn-backend python -m app.scripts.import_certs 2>&1 | tee /tmp/import-certs.log | grep -v "bcrypt"; then
    log_error "证书导入失败，查看日志:"
    cat /tmp/import-certs.log
    exit 1
fi

# 验证导入结果
CERT_COUNT=$(docker exec ovpn-backend python -c "
from app.db.session import SessionLocal
from app import crud
db = SessionLocal()
certs = crud.certificate.get_multi(db, limit=100)
print(len(certs))
db.close()
" 2>&1 | grep -v "bcrypt" | tail -1)

log_info "✓ 证书导入完成 (导入 $CERT_COUNT 个证书)"

if [[ "$CERT_COUNT" == "0" ]]; then
    log_warn "警告: 没有导入任何证书,请检查 Easy-RSA 目录"
    log_warn "Easy-RSA 路径: $EASYRSA_PATH/pki/issued/"
    docker exec ovpn-backend ls -la /etc/openvpn/server/easy-rsa/pki/issued/ || true
fi

# 检查服务状态
BACKEND_STATUS=$($COMPOSE_CMD ps backend | grep -c "Up" || echo "0")
FRONTEND_STATUS=$($COMPOSE_CMD ps frontend | grep -c "Up" || echo "0")

echo ""
echo "=========================================="
if [[ "$BACKEND_STATUS" == "1" && "$FRONTEND_STATUS" == "1" ]]; then
    echo -e "${GREEN}✓ 部署成功！${NC}"
    echo "=========================================="
    echo ""
    echo "📍 访问地址:"
    echo "   Web 界面: http://$PUBLIC_IP:8080/ovpnmanager/"
    echo "   后端健康: http://$PUBLIC_IP:8000/api/health/live"
    echo ""
    echo "👤 管理员账号:"
    echo "   用户名: $ADMIN_USERNAME"
    echo "   密码: $ADMIN_PASSWORD"
    echo ""
    echo "📊 管理命令:"
    echo "   查看日志: $COMPOSE_CMD logs -f"
    echo "   重启服务: $COMPOSE_CMD restart"
    echo "   停止服务: $COMPOSE_CMD stop"
    echo "   启动服务: $COMPOSE_CMD start"
    echo ""
    echo "📁 重要文件:"
    echo "   配置文件: $(pwd)/backend/.env"
    echo "   数据库: $(pwd)/backend/data/app.db"
    echo ""
else
    echo -e "${RED}✗ 部署失败${NC}"
    echo "=========================================="
    echo ""
    log_error "服务状态异常，查看日志："
    $COMPOSE_CMD logs --tail=50
    exit 1
fi

