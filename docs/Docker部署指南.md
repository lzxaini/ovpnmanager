# Docker 部署指南

## 前置条件

1. **已安装 Docker 和 Docker Compose**
   ```bash
   # CentOS/RHEL
   sudo yum install -y docker docker-compose
   sudo systemctl enable --now docker
   
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose
   sudo systemctl enable --now docker
   ```

2. **OpenVPN 服务已在宿主机运行**
   
   **如果使用 angristan 脚本安装**（推荐）：
   ```bash
   # 一键安装（脚本会自动配置所有目录和 Unix Socket）
   curl -O https://raw.githubusercontent.com/angristan/openvpn-install/master/openvpn-install.sh
   chmod +x openvpn-install.sh
   sudo ./openvpn-install.sh
   ```
   
   脚本会自动创建：
   - 证书目录：`/etc/openvpn/server/`
   - Management Socket：`/var/run/openvpn-server/server.sock`（Unix Socket 模式）
   - 状态日志：`/var/log/openvpn/status.log`
   - CCD 目录：`/etc/openvpn/ccd`
   
   **如果手动安装**，需确保：
   - systemd 服务名：`openvpn-server@server`（注意是 `openvpn-server`）
   - 在 `server.conf` 中配置 Management 接口（二选一）：
     ```conf
     # 方式1: Unix Socket（推荐，脚本默认）
     management /var/run/openvpn-server/server.sock unix
     
     # 方式2: TCP Socket（传统方式）
     management 127.0.0.1 7505
     ```

3. **必要目录权限**
   
   **angristan 脚本用户（已自动创建）**：
   ```bash
   # 脚本已创建，只需验证
   ls -ld /etc/openvpn/server/ /var/run/openvpn-server/ /var/log/openvpn/
   ```
   
   **手动安装用户**：
   ```bash
   # 创建必要目录
   sudo mkdir -p /etc/openvpn/server /etc/openvpn/ccd /etc/openvpn/client-configs
   sudo mkdir -p /var/run/openvpn-server /var/log/openvpn
   sudo chmod 755 /etc/openvpn/ccd /etc/openvpn/client-configs
   sudo chmod 750 /var/run/openvpn-server
   ```

---

## 快速部署

### 1. 克隆项目
```bash
git clone <your-repo-url> ovpnmanager
cd ovpnmanager
```

### 2. 配置环境变量
编辑 `docker-compose.yml` 中的 `backend` 服务环境变量：

```yaml
environment:
  - SECRET_KEY=你的超级密钥  # 必须修改！
  - DEFAULT_ADMIN_PASSWORD=强密码  # 默认管理员密码
  - PUBLIC_IP=你的公网IP  # 客户端连接地址
  - PUBLIC_PORT=1194  # OpenVPN 端口
  
  # === 关键配置：根据 OpenVPN 安装方式选择 ===
  # angristan 脚本用户（Unix Socket 模式）
  - OPENVPN_SERVICE_NAME=openvpn-server@server
  - OPENVPN_MANAGEMENT_SOCKET=/var/run/openvpn-server/server.sock
  - OPENVPN_BASE_PATH=/etc/openvpn
  - EASYRSA_PATH=/etc/openvpn/server/easy-rsa
  - OPENVPN_STATUS_PATH=/var/log/openvpn/status.log
  - OPENVPN_CRL_PATH=/etc/openvpn/server/crl.pem
  - TA_KEY_PATH=/etc/openvpn/server/ta.key
  - SERVER_CONF_PATH=/etc/openvpn/server/server.conf
  
  # 手动安装用户（TCP Socket 模式，取消注释下面两行）
  # - OPENVPN_MANAGEMENT_HOST=127.0.0.1
  # - OPENVPN_MANAGEMENT_PORT=7505
  
  - CORS_ORIGINS=["http://你的域名或IP"]
```

**配置说明**：
| 参数 | angristan 脚本 | 手动安装（示例） |
|------|---------------|-----------------|
| `OPENVPN_SERVICE_NAME` | `openvpn-server@server` | `openvpn@server` |
| `OPENVPN_MANAGEMENT_SOCKET` | `/var/run/openvpn-server/server.sock` | （不使用） |
| `OPENVPN_MANAGEMENT_HOST` | （不使用） | `127.0.0.1` |
| `OPENVPN_MANAGEMENT_PORT` | （不使用） | `7505` |
| `EASYRSA_PATH` | `/etc/openvpn/server/easy-rsa` | `/etc/openvpn/easy-rsa` |

### 3. 一键启动
```bash
docker-compose up -d
```

### 4. 查看日志
```bash
# 实时查看所有服务日志
docker-compose logs -f

# 只看后端
docker-compose logs -f backend

# 只看前端
docker-compose logs -f frontend
```

### 5. 访问系统
- **Web 界面**：`http://你的服务器IP/ovpnmanager/`
- **API 文档**：`http://你的服务器IP:8000/api/openapi.json`
- **默认账号**：`admin / admin456`（首次登录后请修改）

---

## 服务管理

```bash
# 停止服务
docker-compose stop

# 启动服务
docker-compose start

# 重启服务
docker-compose restart

# 停止并删除容器（数据保留）
docker-compose down

# 停止并删除容器+数据卷
docker-compose down -v

# 重新构建镜像
docker-compose build --no-cache

# 重新构建并启动
docker-compose up -d --build
```

---

## 目录映射说明

**angristan 脚本用户**：

| 宿主机路径 | 容器路径 | 说明 | 权限 |
|-----------|---------|------|------|
| `./backend/data` | `/app/data` | SQLite 数据库 | 读写 |
| `/etc/openvpn/server` | `/etc/openvpn/server` | 证书和配置 | 只读 |
| `/var/log/openvpn` | `/var/log/openvpn` | OpenVPN 日志 | 只读 |
| `/var/run/openvpn-server` | `/var/run/openvpn-server` | Unix Socket | 读写 |
| `/etc/openvpn/ccd` | `/etc/openvpn/ccd` | 客户端 CCD 配置 | 读写 |
| `/etc/openvpn/client-configs` | `/etc/openvpn/client-configs` | 导出的 .ovpn 文件 | 读写 |

**手动安装用户**：

| 宿主机路径 | 容器路径 | 说明 | 权限 |
|-----------|---------|------|------|
| `./backend/data` | `/app/data` | SQLite 数据库 | 读写 |
| `/etc/openvpn` | `/etc/openvpn` | OpenVPN 配置 | 只读 |
| `/var/log/openvpn` | `/var/log/openvpn` | OpenVPN 日志 | 只读 |
| `/etc/openvpn/ccd` | `/etc/openvpn/ccd` | 客户端 CCD 配置 | 读写 |
| `/etc/openvpn/client-configs` | `/etc/openvpn/client-configs` | 导出的 .ovpn 文件 | 读写 |

---

## 常见问题

### 1. 无法连接 Management 接口
**现象**：后端日志显示 `Connection refused` 或 `Timeout`

**诊断步骤**：
```bash
# 1. 检查 OpenVPN 服务状态
systemctl status openvpn-server@server  # angristan 脚本
# 或
systemctl status openvpn@server  # 手动安装

# 2. 检查 Management 接口类型
grep management /etc/openvpn/server/server.conf

# 3. 如果是 Unix Socket，检查权限
ls -l /var/run/openvpn-server/server.sock
```

**解决方案**：

**A. angristan 脚本用户（Unix Socket）**：
```yaml
backend:
  network_mode: host  # 必须使用 host 网络
  volumes:
    - /var/run/openvpn-server:/var/run/openvpn-server  # 挂载 Socket 目录
  environment:
    - OPENVPN_MANAGEMENT_SOCKET=/var/run/openvpn-server/server.sock
```

**B. 手动安装用户（TCP Socket）**：
```yaml
backend:
  network_mode: host
  environment:
    - OPENVPN_MANAGEMENT_HOST=127.0.0.1
    - OPENVPN_MANAGEMENT_PORT=7505
```

**C. 临时切换到 TCP Socket**（修改 server.conf）：
```bash
# 编辑配置文件
sudo nano /etc/openvpn/server/server.conf

# 将 Unix Socket 改为 TCP
# management /var/run/openvpn-server/server.sock unix
management 127.0.0.1 7505

# 重启服务
sudo systemctl restart openvpn-server@server
```

### 2. systemd 命令无效
**现象**：无法启动/停止 OpenVPN 服务

**原因**：容器内无法直接调用宿主机 systemd

**解决方案**：
必须使用 `privileged: true` + `network_mode: host` + 挂载 D-Bus：

```yaml
backend:
  privileged: true
  network_mode: host
  volumes:
    - /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket:ro
    - /run/systemd:/run/systemd:ro  # angristan 脚本需要
```

**验证**：
```bash
# 进入容器测试
docker exec -it ovpn-backend bash
systemctl status openvpn-server@server
```

### 3. 数据库权限问题
**现象**：`PermissionError: [Errno 13] Permission denied: '/app/data/app.db'`

**解决方案**：
```bash
# 修改宿主机目录权限
sudo chown -R 1000:1000 backend/data
# 或
sudo chmod 777 backend/data
```

### 4. 前端访问后端 404
**现象**：浏览器控制台显示 `/api` 请求失败

**解决方案**：
- 确认 Nginx 代理配置正确（已包含在 `frontend/nginx.conf`）
- 检查后端容器是否启动：`docker-compose ps`
- 查看后端日志：`docker-compose logs backend`

### 5. CORS 跨域错误
**现象**：前端请求被浏览器阻止

**解决方案**：
在 `docker-compose.yml` 中添加你的访问域名：
```yaml
environment:
  - CORS_ORIGINS=["http://192.168.1.100","https://yourdomain.com"]
```

---

## 生产环境优化

### 1. 使用 HTTPS
推荐在前端 Nginx 前加一层反向代理（如宿主机 Nginx + Let's Encrypt）：

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### 2. 修改默认密码
首次部署后：
1. 登录系统 `http://your-ip/ovpnmanager/`
2. 进入用户管理修改 admin 密码
3. 重新配置 `docker-compose.yml` 中的 `DEFAULT_ADMIN_PASSWORD`

### 3. 定期备份
```bash
# 备份数据库
docker exec ovpn-backend cp /app/data/app.db /app/data/app.db.backup

# 或直接在宿主机备份
cp backend/data/app.db backend/data/app.db.$(date +%Y%m%d)
```

### 4. 日志轮转
在 `docker-compose.yml` 中添加：
```yaml
backend:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

---

## 更新升级

```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动（保留数据）
docker-compose up -d --build

# 清理旧镜像
docker image prune -f
```

---

## 卸载

```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi ovpnmanager-backend ovpnmanager-frontend

# 删除数据（谨慎操作！）
rm -rf backend/data
```

---

## 技术支持

- 项目地址：<your-repo-url>
- Issue：<your-repo-url>/issues
- 文档：`docs/` 目录
