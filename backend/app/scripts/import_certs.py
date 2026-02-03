#!/usr/bin/env python3
"""
导入 Easy-RSA 已颁发的证书到数据库
适配 angristan openvpn-install.sh 脚本

使用方法:
    docker exec ovpn-backend python -m app.scripts.import_certs
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.deps import get_db_context
from app.services.importer import import_certificates_from_easyrsa, import_openvpn


def main():
    print("=" * 60)
    print("导入 OpenVPN 证书到数据库")
    print("=" * 60)
    print()

    try:
        with get_db_context() as db:
            # 1. 导入服务器配置和 CCD 客户端
            print("步骤 1: 导入服务器配置和 CCD 客户端...")
            try:
                result1 = import_openvpn(db, server_name="local")
                print(f"  ✓ 创建: {result1['created']} 条")
                print(f"  ✓ 更新: {result1['updated']} 条")
            except Exception as e:
                print(f"  ✗ 错误: {str(e)}")
                import traceback
                traceback.print_exc()
            print()

            # 2. 从 Easy-RSA PKI 导入所有证书
            print("步骤 2: 从 Easy-RSA PKI 导入证书...")
            try:
                result2 = import_certificates_from_easyrsa(db)
                print(f"  ✓ 创建: {result2.get('created', 0)} 个证书")
                print(f"  ✓ 跳过: {result2.get('skipped', 0)} 个已存在")
                
                if "error" in result2:
                    print(f"  ✗ 错误: {result2['error']}")
                
                if "errors" in result2:
                    print(f"  ⚠ 部分错误:")
                    for err in result2["errors"][:10]:  # 显示前10个
                        print(f"    - {err}")
            except Exception as e:
                print(f"  ✗ 错误: {str(e)}")
                import traceback
                traceback.print_exc()
            print()

        print("=" * 60)
        print("导入完成!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print("=" * 60)
        print(f"导入失败: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
