# angristan OpenVPN 脚本适配说明

## 问题诊断

如果你使用 angristan 的 `openvpn-install.sh` 脚本安装了 OpenVPN,可能会遇到以下问题:

1. ✗ 客户端列表为空
2. ✗ 证书数量显示为 0
3. ✗ OpenVPN 服务状态显示 unknown
4. ✗ 接口 500 错误

## 根本原因

angristan 脚本默认将客户端证书生成在 `/root/` 目录下,但管理系统数据库中没有这些证书记录。

### angristan 脚本的目录结构:
```
/etc/openvpn/server/
├── server.conf           # 主配置文件
├── easy-rsa/             # Easy-RSA 目录
│   └── pki/
│       └── issued/       # 已颁发的证书
│           ├── server.crt
│           └── client1.crt
├── ca.crt
├── server.crt
└── server.key

/root/                    # 客户端 .ovpn 文件默认存放位置
├── client1.ovpn
└── client2.ovpn

/var/run/openvpn-server/
└── server.sock          # Unix Socket 管理接口
```

## 解决方案

已在 `deploy-docker.sh` 中添加**自动证书导入**功能:

### 自动执行步骤:
1. ✅ 检测 angristan 安装 (服务名: `openvpn-server@server`)
2. ✅ 检测 Easy-RSA 路径 (`/etc/openvpn/server/easy-rsa`)
3. ✅ 检测 Management 接口 (Unix Socket)
4. ✅ 同步管理员账号
5. ✅ **导入 Easy-RSA 已颁发的证书到数据库**

### 手动导入证书 (可选)

如果需要手动重新导入证书:

```bash
# 进入容器执行导入脚本
docker exec ovpnmanager-backend-1 python -m app.scripts.import_certs
```

导入脚本会:
- 扫描 `/etc/openvpn/server/easy-rsa/pki/issued/*.crt`
- 读取证书信息(序列号、有效期)
- 创建证书记录到数据库
- 自动创建对应的客户端记录

## 重新部署

```bash
cd ~/ovpnmanager
git pull origin main
sudo bash deploy-docker.sh
```

部署完成后,系统会自动:
1. 导入所有已颁发的证书
2. 同步客户端列表
3. 显示正确的证书数量

## 验证

访问 Web 界面: `http://你的IP:8080/ovpnmanager/`

应该能看到:
- ✅ 客户端列表显示所有已生成的客户端
- ✅ 证书数量正确显示
- ✅ OpenVPN 服务状态正常
- ✅ 可以查看在线客户端

## 技术细节

### 新增文件:
1. `backend/app/scripts/import_certs.py` - 证书导入脚本
2. `backend/app/services/importer.py` - 增强了证书导入功能

### 修改文件:
1. `deploy-docker.sh` - 添加自动证书导入步骤
2. `backend/.env` - 自动配置正确的服务名和路径

### 导入逻辑:
```python
def import_certificates_from_easyrsa(db: Session):
    # 1. 扫描 Easy-RSA PKI 目录
    issued_dir = Path("/etc/openvpn/server/easy-rsa/pki/issued")
    
    # 2. 遍历所有 .crt 文件
    for cert_file in issued_dir.glob("*.crt"):
        cn = cert_file.stem  # Common Name
        
        # 3. 使用 openssl 读取证书信息
        cert_info = _get_cert_info(cert_file)
        
        # 4. 创建证书记录
        crud.certificate.create(db, cert_create)
        
        # 5. 创建客户端记录
        crud.client.create(db, client_create)
```

## 故障排查

### 1. 如果证书导入失败

查看导入日志:
```bash
docker logs ovpnmanager-backend-1 | grep -A 20 "导入 Easy-RSA"
```

### 2. 如果服务状态仍显示 unknown

检查服务名称配置:
```bash
# 查看配置
docker exec ovpnmanager-backend-1 cat /app/.env | grep SERVICE_NAME

# 应该显示: OPENVPN_SERVICE_NAME=openvpn-server@server
```

### 3. 如果客户端列表仍为空

手动执行导入:
```bash
docker exec -it ovpnmanager-backend-1 python -m app.scripts.import_certs
```

## 参考

- angristan OpenVPN 脚本: https://github.com/angristan/openvpn-install
- Easy-RSA 文档: https://easy-rsa.readthedocs.io/
