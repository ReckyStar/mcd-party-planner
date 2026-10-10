# 麦当劳 MCP 配置指南

本 Skill 依赖麦当劳中国官方 MCP Server。未配置时所有功能无法使用。

## 一、依赖信息

| 项目 | 内容 |
|---|---|
| 名称 | 麦当劳中国 MCP Server |
| 用途 | 为本 Skill 提供门店检索、菜单价格、优惠券、满减规则与营养数据 |
| 接入方式 | WorkBuddy 自定义连接器（MCP） |
| 服务地址 | `https://mcp.mcd.cn` |
| 传输方式 | streamable HTTP |
| 认证方式 | Bearer Token（MCP Token） |
| 官方主页 | https://open.mcd.cn/mcp |
| 官方文档 | https://github.com/M-China/mcd-mcp-server |
| 核验日期 | 2026-10-10 |
| 适用范围 | 活动期内MCP 服务版本 |

## 二、申请 MCP Token

### 前提

中国大陆地区手机号。仅此一项，无需其他账号或开发者资质。

### 步骤

1. 打开 https://open.mcd.cn/mcp
2. 点击右上角【登录】
3. 跳转至登录页面，使用手机号完成验证
4. 登录成功后右上角【登录】按钮变为【控制台】
5. 点击【控制台】，打开控制台弹窗
6. 点击【激活】，申请 MCP Token
7. 阅读并同意服务协议
8. 申请成功后可一键复制 Token

## 三、在 WorkBuddy 中配置

### 步骤

1. 打开 WorkBuddy，左侧边栏【专家·技能·连接器】
2. 选中【连接器】页签
3. 点击右上角【自定义连接器】→【配置 MCP】
4. 填入以下 JSON，将 `YOUR_MCP_TOKEN` 替换为实际 Token：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

5. 点击【保存】
6. 回到【自定义连接器】，将 `mcd-mcp` 【启用】
7. 在对话框中输入需求，确认可调用相应工具

注意：写入配置后不会自动激活。还需在连接器管理页右上角的自定义连接器入口点击【信任】，才会生效。

## 四、验证

配置完成后，在 WorkBuddy 对话框中请求调用 `now-time-info`。返回当前服务器时间即为连通成功。

也可运行本 Skill 的环境检查：

```bash
python scripts/check_environment.py
```

返回 `ready` 表示核心功能可用，`partial` 表示部分功能受限，`needs_setup` 表示必需配置缺失。

## 五、凭据安全

- Token 相当于账号凭证，等同于密码级别的敏感信息
- 只保存在 `~/.workbuddy/mcp.json` 的 `mcpServers.mcd-mcp.headers.Authorization` 字段
- 不写入 Skill 源码、脚本、README、Git 仓库或任何公开文件
- 不在对话中粘贴完整 Token
- 仓库中的 `mcp-config.example.json` 只允许使用 `${MCD_MCP_TOKEN}` 一类环境变量占位符
- 发现 Token 出现在公开位置立即撤销并重新申请

## 六、轮换与撤销

### 轮换

1. 重新登录 https://open.mcd.cn/mcp
2. 进入【控制台】，按官方流程重新申请 Token
3. 用新 Token 替换 `~/.workbuddy/mcp.json` 中的 `Authorization` 值
4. 保存后重新启用 `mcd-mcp`
5. 运行环境检查确认恢复

### 撤销

通过 https://open.mcd.cn/mcp 控制台的官方入口申请撤销 Token。撤销后本 Skill 所有功能立即不可用，需重新申请。

### 失效处理

出现以下任一情况时，按 Token 失效处理：

- 工具返回 `401` 或鉴权失败
- 工具返回 `code=401` 或消息含"登录"、"token"、"auth"相关提示
- 环境检查返回 `unavailable`，原因为 `auth_expired_or_invalid`

处理：重新登录控制台申请新 Token，按轮换步骤更新配置。不要要求用户把 Token 粘贴到对话中。

## 七、故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 工具列表为空 | 未启用或未信任 | 检查连接器页是否已【启用】并完成【信任】 |
| 调用返回鉴权失败 | Token 错误或过期 | 按轮换步骤重新申请 |
| 门店检索失败 | 未配置或该服务不可达 | 运行环境检查，确认 `mcp` 检查项为 ready |
| 配置后仍无法调用 | 未重启或未信任连接器 | 保存后重新启用连接器 |
| 超时 | 网络不可达 | 检查网络后重试，最多重试 2 次 |

持续失败时不要无限重试。按降级规则向用户说明可用范围与限制。

## 八、服务规则

使用本 MCP 即表示同意麦当劳 MCP 服务规则：https://cdn.mcd.cn/cms/pages/MCPServerRules.html

本 Skill 只调用查询类工具，不调用下单、支付、抽奖类工具。
