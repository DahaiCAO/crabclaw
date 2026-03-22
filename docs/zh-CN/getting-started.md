# 快速入门

## 1）安装

```bash
git clone https://github.com/DahaiCAO/crabclaw.git
cd crabclaw
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
```

可选：

```bash
pip install crabclaw-ai
```

## 2）初始化

```bash
crabclaw onboard
```

会自动生成配置、工作区和默认管理员账号。

## 3）配置模型 Provider

编辑 `~/.crabclaw/config.json`：
- 配置 `providers.<name>.apiKey`
- 设置 `agents.defaults.provider`
- 设置 `agents.defaults.model`

## 4）启动

```bash
crabclaw gateway
```

可选启动 Dashboard：

```bash
crabclaw dashboard
```

## 5）登录

- 地址：`http://127.0.0.1:18791`
- 默认账号：`admin / admin2891`

## 6）端到端验证

```bash
python scripts/e2e_multichannel_sync_check.py --help
```

参考：
- [架构设计](architecture.md)
- [多通道说明](channels.md)
- [用户手册](user-guide.md)
