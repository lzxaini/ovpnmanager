#!/bin/bash

# ==========================================
# OpenVPN Web 管理系统 - 完整一键安装脚本
# 适用于全新的 Ubuntu 22.04 / Debian 11+ 系统
# ==========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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
    echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}\n"
}

# 检查是否以 root 运行
if [[ $EUID -ne 0 ]]; then
   log_error "此脚本必须以 root 权限运行"
   echo "请使用: sudo bash $0"
   exit 1
fi

# 显示欢迎信息
clear
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   OpenVPN Web 管理系统 - 完整一键安装脚本               ║
║                                                          ║
║   适用于全新的 Ubuntu 22.04 / Debian 11+ 系统           ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
EOF
echo ""

log_warn "此脚本将执行以下操作："
echo "  1. 更新系统并安装基础工具（git, curl, wget 等）"
echo "  2. 安装 Docker 和 Docker Compose"
echo "  3. 从 GitHub 克隆项目代码"
echo "  4. 引导安装 OpenVPN 服务器（需要手动操作）"
echo "  5. 自动部署 OpenVPN Web 管理后台"
echo ""
read -p "是否继续? [y/N] " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "安装已取消"
    exit 0
fi

# ==================== 步骤 1: 系统环境检查 ====================
log_step "步骤 1/7: 检查系统环境"

# 检测操作系统
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
    log_info "检测到操作系统: $PRETTY_NAME"
else
    log_error "无法检测操作系统类型"
    exit 1
fi

# 检查是否为支持的系统
if [[ "$OS" != "ubuntu" ]] && [[ "$OS" != "debian" ]]; then
    log_warn "此脚本主要为 Ubuntu/Debian 优化，其他系统可能需要调整"
    read -p "是否继续? [y/N] " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ==================== 步骤 2: 安装基础工具 ====================
log_step "步骤 2/7: 安装基础工具"

log_info "更新软件包列表..."
apt-get update -qq

log_info "安装必要的基础工具..."
apt-get install -y -qq \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    apt-transport-https \
    software-properties-common \
    openssl

log_info "✓ 基础工具安装完成"

# ==================== 步骤 3: 安装 Docker ====================
log_step "步骤 3/7: 安装 Docker"

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    log_info "✓ Docker 已安装: $DOCKER_VERSION"
    
    # 检查 Docker Compose V2
    if docker compose version &> /dev/null; then
        log_info "✓ Docker Compose V2 已安装: $(docker compose version)"
    else
        log_warn "Docker Compose V2 未安装，尝试安装..."
        apt-get install -y docker-compose-plugin
    fi
else
    log_info "开始安装 Docker..."
    
    # 卸载旧版本
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # 添加 Docker 官方 GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$OS/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # 添加 Docker 仓库
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装 Docker
    apt-get update -qq
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # 启动 Docker
    systemctl start docker
    systemctl enable docker
    
    log_info "✓ Docker 安装完成: $(docker --version)"
    log_info "✓ Docker Compose 安装完成: $(docker compose version)"
fi

# ==================== 步骤 4: 克隆项目代码 ====================
log_step "步骤 4/7: 克隆项目代码"

INSTALL_DIR="/root/ovpnmanager"

if [[ -d "$INSTALL_DIR" ]]; then
    log_warn "检测到已存在的项目目录: $INSTALL_DIR"
    read -p "是否删除并重新克隆? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        log_info "已删除旧目录"
    else
        log_info "使用现有目录，执行 git pull 更新..."
        cd "$INSTALL_DIR"
        git pull
        log_info "✓ 代码已更新"
    fi
fi

if [[ ! -d "$INSTALL_DIR" ]]; then
    log_info "从 GitHub 克隆项目..."
    git clone https://github.com/lzxaini/ovpnmanager.git "$INSTALL_DIR"
    log_info "✓ 项目克隆完成"
fi

cd "$INSTALL_DIR"

# ==================== 步骤 5: 安装 OpenVPN 服务器 ====================
log_step "步骤 5/7: 安装 OpenVPN 服务器"

if [[ -f /etc/openvpn/server/server.conf ]]; then
    log_info "✓ OpenVPN 服务器已安装"
    
    # 检查服务状态
    if systemctl is-active --quiet openvpn-server@server; then
        log_info "✓ OpenVPN 服务正在运行"
    else
        log_warn "OpenVPN 服务未运行"
        read -p "是否启动服务? [y/N] " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            systemctl start openvpn-server@server
            systemctl enable openvpn-server@server
            log_info "✓ OpenVPN 服务已启动"
        fi
    fi
else
    log_warn "OpenVPN 服务器未安装"
    echo ""
    echo "请按照以下步骤安装 OpenVPN 服务器："
    echo ""
    echo "  1. 运行安装脚本:"
    echo "     ${YELLOW}bash $INSTALL_DIR/openvpn-install.sh${NC}"
    echo ""
    echo "  2. 按照提示选择配置选项（推荐使用默认值）"
    echo ""
    echo "  3. 安装完成后，重新运行此脚本继续部署 Web 管理后台："
    echo "     ${YELLOW}bash $0${NC}"
    echo ""
    
    read -p "是否现在安装 OpenVPN 服务器? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "启动 OpenVPN 安装脚本..."
        sleep 2
        bash "$INSTALL_DIR/openvpn-install.sh interactive"
        
        # 检查是否安装成功
        if [[ -f /etc/openvpn/server/server.conf ]]; then
            log_info "✓ OpenVPN 服务器安装完成"
        else
            log_error "OpenVPN 安装失败或被取消"
            exit 1
        fi
    else
        log_warn "已跳过 OpenVPN 安装"
        echo ""
        echo "请稍后手动安装 OpenVPN 服务器，然后重新运行此脚本："
        echo "  bash $INSTALL_DIR/openvpn-install.sh interactive"
        echo "  bash $0"
        exit 0
    fi
fi

# ==================== 步骤 6: 配置防火墙 ====================
log_step "步骤 6/7: 配置防火墙（可选）"

# 检查是否安装了 ufw
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status | grep -i "status:" | awk '{print $2}')
    if [[ "$UFW_STATUS" == "active" ]]; then
        log_info "检测到 UFW 防火墙已启用"
        read -p "是否开放 Web 管理端口 8080? [y/N] " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ufw allow 8080/tcp comment 'OpenVPN Web Admin'
            log_info "✓ 已开放端口 8080"
        fi
    fi
fi

# 检查是否安装了 firewalld
if command -v firewall-cmd &> /dev/null; then
    if systemctl is-active --quiet firewalld; then
        log_info "检测到 Firewalld 防火墙已启用"
        read -p "是否开放 Web 管理端口 8080? [y/N] " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            firewall-cmd --permanent --add-port=8080/tcp
            firewall-cmd --reload
            log_info "✓ 已开放端口 8080"
        fi
    fi
fi

# ==================== 步骤 7: 部署 Web 管理后台 ====================
log_step "步骤 7/7: 部署 Web 管理后台"

cd "$INSTALL_DIR/web"

# 检查 deploy-web.sh 是否存在
if [[ ! -f "deploy-web.sh" ]]; then
    log_error "未找到 deploy-web.sh 脚本"
    exit 1
fi

# 赋予执行权限
chmod +x deploy-web.sh

log_info "开始部署 Web 管理后台..."
sleep 2

# 执行部署脚本
bash deploy-web.sh

# ==================== 安装完成 ====================
echo ""
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║         🎉 完整安装完成！                                ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
EOF
echo ""

log_info "系统组件安装情况："
echo "  ✓ 基础工具（git, curl, wget 等）"
echo "  ✓ Docker & Docker Compose"
echo "  ✓ OpenVPN 服务器"
echo "  ✓ OpenVPN Web 管理后台"
echo ""

log_info "相关文件路径："
echo "  项目目录:     ${YELLOW}$INSTALL_DIR${NC}"
echo "  OpenVPN 配置: ${YELLOW}/etc/openvpn/server/${NC}"
echo "  Web 配置:     ${YELLOW}$INSTALL_DIR/web/.env${NC}"
echo ""

log_info "常用管理命令："
echo "  查看服务状态: ${YELLOW}cd $INSTALL_DIR/web && docker compose ps${NC}"
echo "  查看后端日志: ${YELLOW}docker logs -f openvpn-web-backend${NC}"
echo "  查看前端日志: ${YELLOW}docker logs -f openvpn-web-frontend${NC}"
echo "  重启服务:     ${YELLOW}cd $INSTALL_DIR/web && docker compose restart${NC}"
echo "  停止服务:     ${YELLOW}cd $INSTALL_DIR/web && docker compose down${NC}"
echo ""

log_info "管理 OpenVPN："
echo "  添加客户端:   ${YELLOW}bash $INSTALL_DIR/openvpn-install.sh${NC}"
echo "  查看服务状态: ${YELLOW}systemctl status openvpn-server@server${NC}"
echo ""

log_warn "安全建议："
echo "  1. 定期更新系统: apt update && apt upgrade"
echo "  2. 修改默认管理员密码"
echo "  3. 配置防火墙规则限制访问来源"
echo "  4. 启用 HTTPS（可使用 Nginx + Let's Encrypt）"
echo "  5. 定期备份配置文件和证书"
echo ""

exit 0
