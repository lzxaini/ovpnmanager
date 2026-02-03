#!/bin/bash

# ==========================================
# 清理旧版 ovpnmanager 项目脚本
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

# 显示警告信息
clear
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║             ⚠️  清理旧版 ovpnmanager 项目               ║
║                                                          ║
║  此脚本将清理旧版本的 Python + FastAPI 项目            ║
║  包括: Docker 容器、镜像、数据库等                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
EOF
echo ""

log_warn "此操作将执行以下清理："
echo "  1. 停止并删除旧版容器 (ovpn-backend, ovpn-frontend)"
echo "  2. 删除旧版 Docker 镜像"
echo "  3. 删除旧版数据库文件 (backend/data/)"
echo "  4. 删除旧版配置文件 (backend/.env)"
echo "  5. 删除旧版 Docker Compose 文件"
echo ""

log_error "⚠️  警告: 此操作不可恢复！"
echo ""

read -p "确认要继续清理吗? 请输入 'YES' 确认: " -r
if [[ $REPLY != "YES" ]]; then
    log_info "取消清理操作"
    exit 0
fi

# ==================== 步骤 1: 检查旧项目 ====================
log_step "步骤 1/5: 检查旧版项目..."

OLD_CONTAINERS=("ovpn-backend" "ovpn-frontend" "ovpnmanager-backend-1" "ovpnmanager-frontend-1")
FOUND_CONTAINERS=()

for container in "${OLD_CONTAINERS[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        FOUND_CONTAINERS+=("$container")
        log_info "发现旧容器: $container"
    fi
done

if [[ ${#FOUND_CONTAINERS[@]} -eq 0 ]]; then
    log_info "✓ 未发现旧版容器"
else
    log_warn "发现 ${#FOUND_CONTAINERS[@]} 个旧版容器"
fi

# 检查旧版目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLD_BACKEND_DIR="$SCRIPT_DIR/../backend"
OLD_FRONTEND_DIR="$SCRIPT_DIR/../frontend"
OLD_COMPOSE_FILE="$SCRIPT_DIR/../docker-compose.yml"

# ==================== 步骤 2: 停止并删除旧容器 ====================
log_step "步骤 2/5: 停止并删除旧版容器..."

if [[ ${#FOUND_CONTAINERS[@]} -gt 0 ]]; then
    for container in "${FOUND_CONTAINERS[@]}"; do
        log_info "停止容器: $container"
        docker stop "$container" 2>/dev/null || true
        
        log_info "删除容器: $container"
        docker rm "$container" 2>/dev/null || true
    done
    log_info "✓ 旧版容器已清理"
else
    log_info "✓ 跳过容器清理（未找到旧容器）"
fi

# 如果存在 docker-compose.yml，尝试使用 compose down
if [[ -f "$OLD_COMPOSE_FILE" ]]; then
    log_info "检测到 docker-compose.yml，执行 compose down..."
    cd "$(dirname "$OLD_COMPOSE_FILE")"
    docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
    log_info "✓ Docker Compose 清理完成"
fi

# ==================== 步骤 3: 删除旧版镜像 ====================
log_step "步骤 3/5: 删除旧版 Docker 镜像..."

OLD_IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'ovpnmanager|ovpn-' || true)

if [[ -n "$OLD_IMAGES" ]]; then
    log_info "发现以下旧版镜像:"
    echo "$OLD_IMAGES"
    echo ""
    read -p "是否删除这些镜像? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$OLD_IMAGES" | while read -r image; do
            log_info "删除镜像: $image"
            docker rmi "$image" 2>/dev/null || log_warn "镜像 $image 删除失败（可能正在使用）"
        done
        log_info "✓ 旧版镜像已清理"
    else
        log_info "跳过镜像清理"
    fi
else
    log_info "✓ 未发现旧版镜像"
fi

# ==================== 步骤 4: 备份并清理数据 ====================
log_step "步骤 4/5: 清理旧版数据和配置..."

# 备份目录
BACKUP_DIR="$SCRIPT_DIR/../backup-$(date +%Y%m%d_%H%M%S)"

# 备份数据库
if [[ -d "$OLD_BACKEND_DIR/data" ]]; then
    log_info "发现旧版数据库目录"
    read -p "是否备份数据库文件? [Y/n] " -r
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        mkdir -p "$BACKUP_DIR"
        cp -r "$OLD_BACKEND_DIR/data" "$BACKUP_DIR/"
        log_info "✓ 数据库已备份到: $BACKUP_DIR/data"
    fi
    
    read -p "是否删除旧数据库? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$OLD_BACKEND_DIR/data"
        log_info "✓ 旧数据库已删除"
    else
        log_info "保留旧数据库"
    fi
fi

# 备份配置文件
if [[ -f "$OLD_BACKEND_DIR/.env" ]]; then
    log_info "发现旧版配置文件"
    read -p "是否备份配置文件? [Y/n] " -r
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        mkdir -p "$BACKUP_DIR"
        cp "$OLD_BACKEND_DIR/.env" "$BACKUP_DIR/backend.env"
        log_info "✓ 配置文件已备份到: $BACKUP_DIR/backend.env"
    fi
    
    read -p "是否删除旧配置文件? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$OLD_BACKEND_DIR/.env"
        log_info "✓ 旧配置文件已删除"
    else
        log_info "保留旧配置文件"
    fi
fi

# 清理 docker-compose.yml
if [[ -f "$OLD_COMPOSE_FILE" ]]; then
    read -p "是否删除旧版 docker-compose.yml? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$OLD_COMPOSE_FILE"
        log_info "✓ 旧版 docker-compose.yml 已删除"
    else
        log_info "保留 docker-compose.yml"
    fi
fi

# ==================== 步骤 5: 清理完成 ====================
log_step "步骤 5/5: 清理完成"

# 显示清理结果
echo ""
log_info "清理结果汇总:"
echo ""

if [[ ${#FOUND_CONTAINERS[@]} -gt 0 ]]; then
    echo "  ✓ 已清理 ${#FOUND_CONTAINERS[@]} 个旧版容器"
fi

if [[ -n "$OLD_IMAGES" ]]; then
    echo "  ✓ 已清理旧版 Docker 镜像"
fi

if [[ -d "$BACKUP_DIR" ]]; then
    echo "  ✓ 备份文件保存在: ${GREEN}$BACKUP_DIR${NC}"
fi

echo ""
log_info "旧版项目清理完成！"
echo ""

# 建议后续操作
log_info "后续操作建议:"
echo "  1. 部署新版 Web 管理后台:"
echo "     ${YELLOW}cd $(dirname "$SCRIPT_DIR")/web && ./deploy-web.sh${NC}"
echo ""
echo "  2. 如需恢复旧版数据，备份位于:"
echo "     ${YELLOW}$BACKUP_DIR${NC}"
echo ""

# 询问是否立即部署新版
if [[ -f "$SCRIPT_DIR/deploy-web.sh" ]]; then
    echo ""
    read -p "是否立即部署新版 Web 管理后台? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "开始部署新版..."
        bash "$SCRIPT_DIR/deploy-web.sh"
    fi
fi

exit 0
