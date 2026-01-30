# Antigravity API Skill (高级 AI 调度)

本技能通过集成 [Antigravity-Manager](https://github.com/lbjlaq/Antigravity-Manager) 为 Agent 提供顶级 AI 模型支持，包括 Claude 3.7/4.5、Gemini 2.0/3 以及 Imagen 3 高清生图。

## 🌟 核心能力
- **高级对话**: 默认使用 `gemini-3-flash`，支持切换至 `claude-sonnet-4-5` 或 `gemini-3-pro-high`。
- **高清绘图 (banana)**: 使用 Imagen 3 模型生成 4K 画质图像，支持 `16:9`、`9:16`、`1:1` 等多种画幅。
- **参考生图 (Img2Img)**: 支持通过本地图片路径作为参考，实现风格化创作。
- **视频理解 (Video-to-Text)**: 支持传入本地短视频（100MB以内），建议使用 `gemini-3-pro` 模型以获得最佳解说与分析效果。
- **模型管理**: 可实时列出当前网关支持的所有可用模型。

## 🛠️ 首次使用配置指南

### 1. 安装 Skill

请在您的项目根目录下，打开终端 (Terminal) 运行以下命令：
```bash
git clone https://github.com/luoluoluo22/antigravity-api-skill.git .agent/skills/antigravity-api-skill
```

### 2. 准备环境
*   下载并运行 [Antigravity-Manager](https://github.com/lbjlaq/Antigravity-Manager)。
*   在 Manager 中配置好您的 API 账号。

### 3. 配置插件
*   进入本目录 `libs/data/`。
*   如果不存在 `config.json`，请复制 `config.example.json` 并重命名。
*   **默认配置**:
    *   `base_url`: `http://127.0.0.1:8045/v1`
    *   `api_key`: `sk-antigravity`

### 4. 连接验证
安装并配置完成后，您可以直接在 AI 助手中发送指令：
> "Antigravity 技能配置好了吗？帮我查看一下支持的模型。"

---

## 📖 技能使用 (AI 对话)
安装并配置完成后，您无需手动运行脚本，直接在对话框中给 AI 发指令即可。

### 🗣️ 试试这样问 AI
- **高级写作**: "请用 Claude 4.5 帮我写一个短视频脚本。"
- **高清绘图**: "用 banana 生成一张 16:9 的赛博朋克城市背景图。"
- **参考生图**: "参考这张图 [绝对路径]，帮我画一个类似风格的饕餮巨兽。"
- **查看模型**: "查看现在有哪些模型可以用。"
- **推荐**: 对于视频理解任务，请直接对 AI 说 "使用 gemini-3-pro 分析这个视频..."。

## 📂 目录结构
- `scripts/`: 核心执行脚本 (Chat, Image, List)。
- `libs/`: API 客户端封装。
- `generated_assets/`: 默认图片输出路径。
