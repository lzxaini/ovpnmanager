#!/bin/bash
# 部署检查脚本 - 用于诊断问题

echo "=========================================="
echo "OpenVPN Manager 部署诊断"
echo "=========================================="
echo ""

echo "1. 检查容器状态..."
docker ps -a | grep ovpn

echo ""
echo "2. 检查后端日志 (最近30行)..."
docker logs ovpn-backend --tail 30

echo ""
echo "3. 检查 Easy-RSA 目录..."
docker exec ovpn-backend ls -la /etc/openvpn/server/easy-rsa/pki/issued/ 2>/dev/null || echo "目录不存在或无法访问"

echo ""
echo "4. 检查数据库中的证书..."
docker exec ovpn-backend python -c "
from app.db.session import SessionLocal
from app import crud

db = SessionLocal()
certs = crud.certificate.get_multi(db, limit=100)
clients = crud.client.get_multi(db, limit=100)

print(f'数据库中的证书数量: {len(certs)}')
print(f'数据库中的客户端数量: {len(clients)}')

if certs:
    print('证书列表:')
    for cert in certs[:5]:
        print(f'  - {cert.common_name} (序列号: {cert.serial_number})')
        
if clients:
    print('客户端列表:')
    for client in clients[:5]:
        print(f'  - {client.common_name} (状态: {client.status})')

db.close()
" 2>&1 | grep -v "bcrypt"

echo ""
echo "5. 检查后端配置..."
docker exec ovpn-backend cat /app/.env | grep -E "SERVICE_NAME|EASYRSA_PATH|MANAGEMENT"

echo ""
echo "6. 测试 systemctl 命令..."
docker exec ovpn-backend systemctl status openvpn-server@server --no-pager 2>&1 | head -10 || echo "systemctl 命令失败"

echo ""
echo "=========================================="
echo "诊断完成"
echo "=========================================="
