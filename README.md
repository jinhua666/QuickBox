# QuickBox

QuickBox 是 Windows 本地个人信息管理工具。支持网站、账号密码、命令和文档链接，以及搜索、收藏、排序、编辑、复制与打开。

## 数据与安全

数据保存在 `%LOCALAPPDATA%\QuickBox\data.db`，与安装目录分开，安装和卸载不会删除此目录。首次使用需要设置主密码；**主密码遗失后无法恢复已加密的密码**。密码使用 Scrypt 派生密钥和 AES-256-GCM 加密；名称、链接、用户名、命令和备注以明文存储。复制密码 30 秒后或正常退出程序时，仅当剪贴板仍是该内容时清除。请自行备份整个数据目录，并妥善保管备份和主密码。

数据库通过 SQLite `user_version` 管理结构版本；未来结构迁移应先使用 SQLite 备份 API 保存备份，拒绝打开更高版本。当前是第一个数据库版本。

## 开发运行

需要 64 位 Python 3.10–3.12。建立虚拟环境并安装 `requirements-build.txt`，然后运行：

```powershell
python -m quickbox
python -m pytest tests -q
```

构建安装程序需要 PyInstaller 和 Inno Setup 6。安装依赖后运行 `./build.ps1`；若 ISCC 不在默认路径，传入 `-Iscc "路径\ISCC.exe"`。产物在 `dist`，仅供本地使用。安装程序仅管理安装目录，数据目录不属于安装清单。

## 版本与发布

版本在 `quickbox/version.py` 统一维护；更新历史见 `CHANGELOG.md`。私有仓库为 https://github.com/jinhua666/QuickBox。更新检查、私有仓库安全认证及安装包校验尚未实现，见 [架构设计](docs/architecture.md)。只有获得用户明确许可后才能推送发布代码、打标签、创建 Release 或上传安装包。
