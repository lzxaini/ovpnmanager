# 前端 Dockerfile - 多阶段构建
# 阶段 1: 构建前端
FROM node:18-alpine AS builder

WORKDIR /app

# 复制 package.json 并安装依赖
COPY package*.json ./
RUN npm install

# 复制源码并构建
COPY . .
RUN npm run build

# 阶段 2: Nginx 静态服务
FROM nginx:1.25-alpine

# 复制构建产物到 Nginx 目录
COPY --from=builder /app/ovpnmanager /usr/share/nginx/html/ovpnmanager

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
