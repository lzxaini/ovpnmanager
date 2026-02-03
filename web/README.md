# OpenVPN Web 管理后台

这是一个基于 Vue 3 + Node.js + Docker 的 OpenVPN Web 管理界面，用于在线管理 OpenVPN 服务器和客户端。

## ✨ 功能特性

- 🔐 **安全登录认证** - JWT Token 身份验证
- 👥 **客户端管理** - 添加、删除、吊销、续期客户端证书
- 📥 **配置下载** - 在线下载客户端 .ovpn 配置文件
- 📊 **服务器监控** - 实时查看在线客户端和流量统计
- 🔄 **证书管理** - 服务器和客户端证书续期
- 🐳 **Docker 部署** - 一键启动，无需复杂配置

## 🛠 技术栈

### 前端
- Vue 3
- Vue Router
- Pinia (状态管理)
- Element Plus (UI 组件库)
- Axios (HTTP 客户端)
- Vite (构建工具)

### 后端
- Node.js
- Express
- JWT (身份认证)
- bcryptjs (密码加密)

## 📋 前置要求

- Docker & Docker Compose
- 已安装并配置好的 OpenVPN 服务器（使用本项目的 openvpn-install.sh 脚本）

## 🚀 快速开始

### 1. 配置环境变量

```bash
cd web
cp .env.example .env
```

编辑 `.env` 文件，修改以下配置：

```env
# JWT 密钥（必须修改！）
JWT_SECRET=your-super-secret-jwt-key-change-this

# 管理员账号（必须修改！）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# 端口配置
BACKEND_PORT=3000
FRONTEND_PORT=8080
```

### 2. 启动服务

```bash
# 在 web 目录下执行
docker-compose up -d
```

### 3. 访问管理后台

打开浏览器访问：`http://your-server-ip:8080`

默认登录凭据（请务必修改）：
- 用户名：`admin`
- 密码：`admin123`

## 📁 项目结构

```
web/
├── backend/                 # 后端 Node.js API
│   ├── routes/             # API 路由
│   │   ├── auth.js         # 认证路由
│   │   ├── clients.js      # 客户端管理路由
│   │   └── server.js       # 服务器管理路由
│   ├── middleware/         # 中间件
│   │   └── auth.js         # JWT 认证中间件
│   ├── utils/              # 工具函数
│   │   └── scriptExecutor.js  # 脚本执行器
│   ├── server.js           # 服务器入口
│   ├── package.json
│   └── Dockerfile
│
├── frontend/               # 前端 Vue 应用
│   ├── src/
│   │   ├── views/          # 页面组件
│   │   │   ├── Login.vue   # 登录页
│   │   │   ├── Dashboard.vue  # 主面板
│   │   │   ├── Clients.vue    # 客户端管理
│   │   │   └── Server.vue     # 服务器状态
│   │   ├── stores/         # Pinia 状态管理
│   │   │   └── auth.js     # 认证状态
│   │   ├── router/         # 路由配置
│   │   │   └── index.js
│   │   ├── utils/          # 工具函数
│   │   │   └── api.js      # API 封装
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   ├── vite.config.js
│   ├── nginx.conf
│   └── Dockerfile
│
├── docker-compose.yml      # Docker Compose 配置
├── .env.example            # 环境变量示例
└── README.md               # 本文件
```

## 🔌 API 接口

### 认证接口

- `POST /api/auth/login` - 登录
- `POST /api/auth/verify` - 验证 Token

### 客户端管理

- `GET /api/clients` - 获取客户端列表
- `POST /api/clients` - 添加客户端
- `DELETE /api/clients/:name` - 吊销客户端
- `POST /api/clients/:name/renew` - 续期客户端
- `POST /api/clients/:name/disconnect` - 强制断开在线客户端 ⭐
- `GET /api/clients/:name/config` - 下载客户端配置

### 服务器管理

- `GET /api/server/status` - 获取服务器状态
- `GET /api/server/info` - 获取服务器信息
- `POST /api/server/renew` - 续期服务器证书

## 🔒 安全建议

1. **必须修改默认密码** - 在生产环境中务必修改 `.env` 中的 `ADMIN_PASSWORD`
2. **修改 JWT 密钥** - 使用强随机字符串作为 `JWT_SECRET`
3. **使用 HTTPS** - 建议配置反向代理（如 Nginx）并启用 SSL/TLS
4. **限制访问** - 使用防火墙限制只有可信 IP 可以访问管理后台
5. **定期备份** - 定期备份 OpenVPN 配置和证书文件

## 🛡️ 防火墙配置（可选）

如果需要限制管理后台访问，可以配置防火墙规则：

```bash
# 只允许特定 IP 访问管理后台
iptables -A INPUT -p tcp --dport 8080 -s YOUR_IP_ADDRESS -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

## 🔧 开发模式

### 后端开发

```bash
cd backend
npm install
npm run dev
```

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 📝 常见问题

### Q: 无法连接到 API

A: 检查后端容器是否正常运行：`docker-compose logs backend`

### Q: 无法执行 OpenVPN 脚本

A: 确保：
1. Docker 容器有足够的权限（`privileged: true`）
2. OpenVPN 已正确安装在宿主机上
3. 脚本路径配置正确

### Q: 无法下载客户端配置

A: 检查客户端配置文件是否生成在正确的目录（默认 `/root`）

## 📜 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## ⚠️ 免责声明

本项目仅供学习和个人使用。在生产环境中使用前，请确保进行充分的安全测试和加固。

---

**注意**：首次使用前，请务必修改默认的管理员密码和 JWT 密钥！
