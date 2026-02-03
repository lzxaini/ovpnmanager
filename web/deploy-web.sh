#!/bin/bash

# ==========================================
# OpenVPN Web 管理后台 - 一键部署脚本
# ==========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
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
    echo -e "\n${BLUE}==>${NC} ${BLUE}$1${NC}\n"
}

# 检查是否以 root 运行
if [[ $EUID -ne 0 ]]; then
   log_error "此脚本必须以 root 权限运行"
   exit 1
fi

# 显示欢迎信息
clear
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║       OpenVPN Web 管理后台 - 一键部署脚本               ║
║                                                          ║
║       基于 openvpn-install.sh 的 Web 管理界面           ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
EOF
echo ""

# ==================== 步骤 1: 环境检查 ====================
log_step "步骤 1/6: 检查运行环境..."

# 检查 Docker
if ! command -v docker &> /dev/null; then
    log_error "未检测到 Docker，请先安装 Docker"
    log_info "安装命令: curl -fsSL https://get.docker.com | sh"
    exit 1
fi
log_info "✓ Docker 已安装: $(docker --version | head -1)"

# 检查 Docker Compose
if ! docker compose version &> /dev/null; then
    log_error "未检测到 Docker Compose V2"
    log_info "请升级到 Docker 20.10+ 版本"
    exit 1
fi
log_info "✓ Docker Compose 已安装: $(docker compose version)"

# 检查 openvpn-install.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENVPN_SCRIPT="$SCRIPT_DIR/../openvpn-install.sh"

if [[ ! -f "$OPENVPN_SCRIPT" ]]; then
    log_error "未找到 openvpn-install.sh 脚本"
    log_info "请确保脚本位于: $OPENVPN_SCRIPT"
    exit 1
fi
log_info "✓ openvpn-install.sh 脚本已找到"

# 检查 OpenVPN 是否已安装
if [[ ! -f /etc/openvpn/server/server.conf ]]; then
    log_error "未检测到 OpenVPN 服务器配置"
    log_info "请先运行 openvpn-install.sh 安装 OpenVPN 服务器"
    exit 1
fi
log_info "✓ OpenVPN 服务器已安装"

# 检查 OpenVPN 是否运行
if ! systemctl is-active --quiet openvpn-server@server; then
    log_warn "OpenVPN 服务未运行"
    read -p "是否启动 OpenVPN 服务? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl start openvpn-server@server
        log_info "✓ OpenVPN 服务已启动"
    else
        log_warn "继续部署，但建议先启动 OpenVPN 服务"
    fi
else
    log_info "✓ OpenVPN 服务正在运行"
fi

# ==================== 步骤 2: 配置参数 ====================
log_step "步骤 2/6: 配置管理后台参数..."

# 获取公网 IP
PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "")
if [[ -z "$PUBLIC_IP" ]]; then
    # 尝试从配置文件中读取
    if grep -q "^local" /etc/openvpn/server/server.conf; then
        PUBLIC_IP=$(grep "^local" /etc/openvpn/server/server.conf | awk '{print $2}' | head -1)
    fi
fi

if [[ -z "$PUBLIC_IP" ]]; then
    log_warn "无法自动获取公网 IP"
    read -p "请手动输入服务器 IP 地址: " PUBLIC_IP
fi
log_info "✓ 服务器 IP: $PUBLIC_IP"

# 配置管理员账户
echo ""
read -p "设置管理员用户名 (默认: admin): " ADMIN_USERNAME
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}

while true; do
    read -sp "设置管理员密码 (不少于 6 位): " ADMIN_PASSWORD
    echo ""
    if [[ ${#ADMIN_PASSWORD} -lt 6 ]]; then
        log_error "密码长度不能少于 6 位"
        continue
    fi
    read -sp "再次确认密码: " ADMIN_PASSWORD_CONFIRM
    echo ""
    if [[ "$ADMIN_PASSWORD" == "$ADMIN_PASSWORD_CONFIRM" ]]; then
        break
    else
        log_error "两次密码输入不一致，请重新输入"
    fi
done

# 生成随机 JWT 密钥
JWT_SECRET=$(openssl rand -hex 32)

# 配置端口
echo ""
read -p "设置前端访问端口 (默认: 8080): " FRONTEND_PORT
FRONTEND_PORT=${FRONTEND_PORT:-8080}

read -p "设置后端 API 端口 (默认: 3000): " BACKEND_PORT
BACKEND_PORT=${BACKEND_PORT:-3000}

# ==================== 步骤 3: 生成配置文件 ====================
log_step "步骤 3/6: 生成配置文件..."

cd "$SCRIPT_DIR"

# 备份旧配置
if [[ -f ".env" ]]; then
    cp .env ".env.backup.$(date +%Y%m%d_%H%M%S)"
    log_info "✓ 已备份旧配置"
fi

# 生成 .env 文件
cat > .env <<EOF
# OpenVPN Web 管理后台配置文件
# 自动生成于: $(date '+%Y-%m-%d %H:%M:%S')

# ========== 安全配置 ==========
JWT_SECRET=$JWT_SECRET
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD

# ========== 端口配置 ==========
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT

# ========== 服务器配置 ==========
PUBLIC_IP=$PUBLIC_IP
EOF

log_info "✓ 配置文件已生成: .env"

# 更新 docker-compose.yml 端口映射
if [[ -f "docker-compose.yml" ]]; then
    sed -i.bak "s/\"3000:3000\"/\"$BACKEND_PORT:3000\"/" docker-compose.yml
    sed -i.bak "s/\"8080:80\"/\"$FRONTEND_PORT:80\"/" docker-compose.yml
    log_info "✓ Docker Compose 配置已更新"
fi

# 更新前端 API 地址
cat > frontend/.env.production <<EOF
# 前端生产环境配置
VITE_API_BASE_URL=http://$PUBLIC_IP:$BACKEND_PORT
EOF
log_info "✓ 前端配置已生成"

# ==================== 步骤 4: 停止旧容器 ====================
log_step "步骤 4/6: 停止旧容器（如果存在）..."

if docker ps -a | grep -q "openvpn-web-"; then
    log_info "检测到旧容器，正在停止..."
    docker compose down 2>/dev/null || true
    log_info "✓ 旧容器已停止"
else
    log_info "✓ 未检测到旧容器"
fi

# ==================== 步骤 5: 构建和启动服务 ====================
log_step "步骤 5/6: 构建和启动服务..."

log_info "开始构建 Docker 镜像（首次构建可能需要几分钟）..."
docker compose build --no-cache

log_info "启动服务容器..."
docker compose up -d

# 等待服务启动
log_info "等待服务启动..."
sleep 5

# 检查容器状态
BACKEND_STATUS=$(docker inspect -f '{{.State.Status}}' openvpn-web-backend 2>/dev/null || echo "not found")
FRONTEND_STATUS=$(docker inspect -f '{{.State.Status}}' openvpn-web-frontend 2>/dev/null || echo "not found")

if [[ "$BACKEND_STATUS" == "running" ]] && [[ "$FRONTEND_STATUS" == "running" ]]; then
    log_info "✓ 服务启动成功"
else
    log_error "服务启动失败，请检查日志："
    log_info "  后端日志: docker logs openvpn-web-backend"
    log_info "  前端日志: docker logs openvpn-web-frontend"
    exit 1
fi

# ==================== 步骤 6: 验证部署 ====================
log_step "步骤 6/6: 验证部署..."

# 检查后端健康状态
log_info "检查后端 API..."
sleep 3
if curl -s -f "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
    log_info "✓ 后端 API 正常响应"
else
    log_warn "后端 API 暂时无响应，可能需要更多启动时间"
fi

# 检查前端
log_info "检查前端服务..."
if curl -s -f "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
    log_info "✓ 前端服务正常响应"
else
    log_warn "前端服务暂时无响应，可能需要更多启动时间"
fi

# ==================== 部署完成 ====================
echo ""
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║                 🎉 部署成功！                            ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
EOF
echo ""

log_info "访问地址: ${GREEN}http://$PUBLIC_IP:$FRONTEND_PORT${NC}"
echo ""
log_info "登录凭据:"
echo "  用户名: ${GREEN}$ADMIN_USERNAME${NC}"
echo "  密码: ${GREEN}$ADMIN_PASSWORD${NC}"
echo ""

log_info "常用命令:"
echo "  查看服务状态: ${YELLOW}docker compose ps${NC}"
echo "  查看后端日志: ${YELLOW}docker logs -f openvpn-web-backend${NC}"
echo "  查看前端日志: ${YELLOW}docker logs -f openvpn-web-frontend${NC}"
echo "  重启服务:     ${YELLOW}docker compose restart${NC}"
echo "  停止服务:     ${YELLOW}docker compose down${NC}"
echo ""

log_warn "重要提示:"
echo "  1. 请妥善保管管理员密码"
echo "  2. 建议配置防火墙规则，只允许特定 IP 访问管理后台"
echo "  3. 首次登录后请修改默认密码"
echo ""

# 询问是否在浏览器中打开
read -p "是否现在在浏览器中打开管理后台? [y/N] " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://$PUBLIC_IP:$FRONTEND_PORT"
    elif command -v open &> /dev/null; then
        open "http://$PUBLIC_IP:$FRONTEND_PORT"
    else
        log_info "请手动在浏览器中打开: http://$PUBLIC_IP:$FRONTEND_PORT"
    fi
fi

exit 0
