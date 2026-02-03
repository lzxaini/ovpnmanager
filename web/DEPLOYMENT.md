# 部署和清理脚本使用指南

本目录包含两个独立的脚本，用于管理 OpenVPN Web 管理后台的部署和旧版本清理。

---

## 📜 脚本说明

### 1. `deploy-web.sh` - 一键部署脚本

**功能：** 自动化部署 OpenVPN Web 管理后台

**主要步骤：**
- ✅ 检查运行环境（Docker、Docker Compose、OpenVPN）
- ✅ 配置管理员账户和端口
- ✅ 生成配置文件（.env、前端配置）
- ✅ 构建和启动 Docker 容器
- ✅ 验证部署状态

**使用方法：**
```bash
cd web
sudo bash deploy-web.sh
```

**交互式配置：**
- 管理员用户名（默认: admin）
- 管理员密码（最少 6 位）
- 前端访问端口（默认: 8080）
- 后端 API 端口（默认: 3000）

**部署成功后：**
- 访问地址: `http://你的服务器IP:8080`
- 使用配置的管理员账户登录

---

### 2. `cleanup-old.sh` - 清理旧项目脚本

**功能：** 清理旧版本的 Python + FastAPI 项目

**清理内容：**
- 🗑️ 停止并删除旧版容器（ovpn-backend, ovpn-frontend）
- 🗑️ 删除旧版 Docker 镜像
- 💾 备份并可选删除数据库文件
- 💾 备份并可选删除配置文件
- 🗑️ 删除旧版 docker-compose.yml

**使用方法：**
```bash
cd web
sudo bash cleanup-old.sh
```

**安全特性：**
- ⚠️ 需要输入 `YES` 确认才会执行清理
- 💾 清理前自动备份数据库和配置
- 📁 备份文件保存在 `backup-YYYYMMDD_HHMMSS/` 目录
- 🔄 可选择保留数据和配置文件

---

## 🚀 完整部署流程

### 场景 1：全新部署（从未安装旧版）

```bash
cd web
sudo bash deploy-web.sh
```

### 场景 2：从旧版升级到新版

**步骤 1：清理旧版本**
```bash
cd web
sudo bash cleanup-old.sh
```

按提示操作：
- 输入 `YES` 确认清理
- 选择是否备份数据（建议备份）
- 选择是否删除旧配置（可以删除）

**步骤 2：部署新版本**
```bash
sudo bash deploy-web.sh
```

**或者在清理完成后直接选择立即部署**

---

## 📋 常用命令

### 查看服务状态
```bash
cd web
docker compose ps
```

### 查看日志
```bash
# 查看后端日志
docker logs -f openvpn-web-backend

# 查看前端日志
docker logs -f openvpn-web-frontend
```

### 重启服务
```bash
cd web
docker compose restart
```

### 停止服务
```bash
cd web
docker compose down
```

### 更新服务
```bash
cd web
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## ⚙️ 配置文件说明

### `.env` - 主配置文件

由 `deploy-web.sh` 自动生成，包含：

```env
# 安全配置
JWT_SECRET=随机生成的密钥
ADMIN_USERNAME=你设置的用户名
ADMIN_PASSWORD=你设置的密码

# 端口配置
BACKEND_PORT=3000
FRONTEND_PORT=8080

# 服务器配置
PUBLIC_IP=自动检测的公网IP
```

### `frontend/.env.production` - 前端配置

自动生成，配置后端 API 地址：
```env
VITE_API_BASE_URL=http://你的IP:3000
```

---

## 🔒 安全建议

1. **修改默认端口**
   - 建议将前端端口改为非标准端口
   - 使用防火墙限制访问源 IP

2. **强密码策略**
   - 管理员密码至少 12 位
   - 包含大小写字母、数字和特殊字符

3. **定期备份**
   ```bash
   # 备份当前配置
   cp web/.env web/.env.backup.$(date +%Y%m%d)
   ```

4. **限制访问**
   ```bash
   # 使用 iptables 限制访问（示例）
   iptables -A INPUT -p tcp --dport 8080 -s 你的IP地址 -j ACCEPT
   iptables -A INPUT -p tcp --dport 8080 -j DROP
   ```

---

## 🐛 故障排查

### 问题 1：容器启动失败

**检查日志：**
```bash
docker logs openvpn-web-backend
docker logs openvpn-web-frontend
```

**常见原因：**
- 端口已被占用
- Docker 权限不足
- OpenVPN 未安装或未运行

### 问题 2：无法访问管理后台

**检查步骤：**
```bash
# 1. 检查容器是否运行
docker ps | grep openvpn-web

# 2. 检查端口是否开放
netstat -tlnp | grep 8080

# 3. 检查防火墙
ufw status
firewall-cmd --list-ports
```

### 问题 3：API 请求失败

**检查配置：**
```bash
# 查看前端配置
cat web/frontend/.env.production

# 确保 API 地址正确
curl http://localhost:3000/api/health
```

---

## 📞 获取帮助

- **查看容器状态：** `docker compose ps`
- **查看实时日志：** `docker compose logs -f`
- **重新部署：** 运行 `deploy-web.sh` 会自动停止旧容器并重新部署

---

## 🔄 回滚到旧版本

如果需要恢复旧版本：

1. **找到备份目录：**
   ```bash
   ls -la ~/ovpnmanager/backup-*
   ```

2. **恢复数据：**
   ```bash
   cp -r backup-YYYYMMDD_HHMMSS/data backend/
   cp backup-YYYYMMDD_HHMMSS/backend.env backend/.env
   ```

3. **重新部署旧版：**
   ```bash
   cd ~/ovpnmanager
   bash deploy-docker.sh
   ```

---

## ✅ 完成检查清单

部署完成后，请确认：

- [ ] 能够访问 `http://服务器IP:8080`
- [ ] 能够使用管理员账户登录
- [ ] 能够查看客户端列表
- [ ] 能够添加新客户端
- [ ] 能够下载 .ovpn 配置文件
- [ ] 能够查看服务器状态
- [ ] 能够看到在线客户端（如果有）

---

**祝你使用愉快！** 🎉
