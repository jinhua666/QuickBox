# QuickBox 架构设计

## 范围

QuickBox 是仅在 Windows 本地运行的个人信息工具。首版支持网站、账号密码、命令和文档链接，统一条目模型、分类、搜索、收藏、排序、增删改、复制与打开。没有云同步。

## 组件

- `quickbox/storage.py`：SQLite 数据库、版本检查和迁移备份、条目持久化、主密码与加密。
- `quickbox/ui.py`：PySide6 解锁、导航、列表、详情和编辑操作；依赖存储层而不直接操作 SQLite。
- `quickbox/updates.py`：预留 GitHub Release 检查接口；私有仓库需要用户提供安全凭据，不能内置令牌。
- `quickbox/__main__.py`：程序启动入口。`quickbox/version.py` 是版本号唯一来源。
- `installer/`：PyInstaller 和 Inno Setup 的本地构建配置；安装和卸载只处理程序文件。

## 存储与安全

数据位于 `%LOCALAPPDATA%/QuickBox/data.db`，不在安装目录。用 SQLite `user_version` 标识数据库结构；迁移现有数据库前以 SQLite 备份 API 创建独立备份，拒绝打开更高版本的数据库。首次创建时生成随机盐，用 Scrypt 派生 256 位密钥，使用 AES-256-GCM 加密验证标记和每个密码。遗失主密码无法恢复。名称、地址、用户名、命令和备注不加密，属于本机明文元数据。密码复制 30 秒后仅在剪贴板仍保留原内容时清空。

## 发布与更新

本地阶段构建不发布。正式发布必须先获得用户明确许可，再确定版本、构建、提交推送、打标签和创建 Release。更新模块应读取 GitHub 正式 Release 并严格校验版本和安装包；私有仓库授权采用系统凭据存储，不能将令牌写进代码或安装包。安装和升级不得触及用户数据。仓库和凭据、安装包校验及用户确认流程未完成前，不应自动安装下载的文件。
