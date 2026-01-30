---
name: antigravity-skill
description: 当用户需要使用 Antigravity API (Gemini 3 Flash, Claude 3.7/4.5 文本生成, banana生图) 时使用此技能。
---

# Antigravity Skill

## 目标
利用 Antigravity API 网关提供的加强版 AI 能力，包括 **Gemini 3 Flash / Pro**, **Claude 3.5/3.7 Sonnet** 的高级文本生成与 **Gemini 3 Pro Image (Imagen 3)** 的 4K 绘图能力。

## 场景
- **高级对话**: 使用 Gemini 3 或 Claude 3.7 进行复杂逻辑分析、脚本编写。
- **高清绘图**: 生成 16:9 4K 质量的视频素材、封面图 (优于普通绘图)。

## 环境配置 (Setup)

### 首次使用配置指南
本技能依赖本地运行的 **Antigravity Manager** 服务。首次使用请按以下步骤配置：

1.  **下载并安装服务**:
    *   前往项目地址下载最新版客户端: [Antigravity-Manager Releases](https://github.com/lbjlaq/Antigravity-Manager)
    *   安装并启动 Windows 客户端。

2.  **配置连接**:
    *   确保本地服务已启动 (默认端口 `:8045`)。
    *   配置文件位于 `libs/data/config.json`。
    *   **Base URL**: `http://127.0.0.1:8045/v1`
    *   **API Key**: `sk-antigravity` (默认) 或您自己在客户端设置的 Key。

3.  **验证连接**:
    *   运行指令 "查看所有模型" 来测试服务是否联通。

## 指令

### 1. 高级对话 (Chat)
**指令**: "请用 Claude 4.5 写一段脚本..."
- **执行**: `python scripts/chat.py "{Prompt}" "{ModelName}"`
- **默认模型**: `gemini-3-flash`
- **可选模型**: `claude-3-7-sonnet`, `gemini-2.0-flash-thinking`

### 2. 高清绘图 (Imagen 3 / banana)
**指令**: "用 banana 画一张..." / "生成一张 16:9 的高清图..."
- **执行**: `python scripts/generate_image.py "{Prompt}" "{Size/Ratio}"`
- **参数**:
  - `Prompt`: 描述词
  - `Size`: 支持 `16:9`, `9:16`, `1:1` 或具体分辨率 `1920x1080`。

### 3. 查看可用模型 (List Models)
**指令**: "查看所有模型" / "有什么模型可以用"
- **执行**: `python scripts/list_models.py`

## 注意事项
- 绘图默认开启 HD (4K) 质量。
- 图片保存在根目录 `generated_assets/`。
