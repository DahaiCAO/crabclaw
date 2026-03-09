# 安全（中文）

<p align="center">
  <a href="../en/security.md"><strong>English</strong></a> | <a href="../zh-CN/security.md"><strong>中文</strong></a>
</p>

生产环境建议：
- 设置 `"restrictToWorkspace": true` 将所有工具限制在 workspace 目录内。
- 不同版本的默认访问策略可能不同；若需开放给所有用户，设置 `"allowFrom": ["*"]`。

常用选项：
| 选项 | 默认值 | 说明 |
|------|--------|-----|
| `tools.restrictToWorkspace` | `false` | 限制文件/命令工具在 workspace 范围 |
| `tools.exec.pathAppend` | `""` | 运行命令时附加 PATH 路径 |
| `channels.*.allowFrom` | `[]` | 用户白名单；`["*"]` 表示开放 |

更多细节见 [README.md](../../README.md)。
