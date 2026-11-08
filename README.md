# 电商AI内容生产工具

输入产品图片和规格，自动生成宣传文案、分镜头脚本和AI宣传视频。

## 快速开始

### 1. 安装依赖

```bash
pip install --break-system-packages -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 SophNet API Key
```

或启动后在设置页面（/settings）中配置。

### 3. 启动

```bash
python app.py
```

访问 http://localhost:8080

## 功能

- 📸 **图片分析**: 上传产品图，Vision 模型自动识别品类、材质、风格
- ✍️ **文案生成**: 自动生成商品标题、卖点描述、营销提示词、详情页文案
- 🎬 **分镜头脚本**: 生成 5-8 个分镜头，含运镜描述和中英文视频 prompt
- 🎥 **视频生成**: 调用 WAN2.7 / HappyHorse 生成宣传视频片段

## 支持的模型

| 类型 | 模型 |
|------|------|
| LLM (视觉) | DeepSeek-V4-Flash-Vision-Exp |
| LLM (文本) | GLM-4-Flash, Kimi |
| 视频生成 | WAN 2.7, HappyHorse-1.1-i2v |

## 技术栈

- FastAPI + Jinja2 + HTMX + Pico.css
- SQLite + SQLAlchemy (async)
- SophNet 算力平台 API