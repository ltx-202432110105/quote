# Competition PPTX Generator

本仓库提供脚本，可将仓库内 Markdown（按页总结内容）自动生成灰白科技数码风 PPTX，并统一为 16:9 主题风格。

## 输入来源

- Markdown 内容源：`/home/runner/work/quote/quote/CareerPlanner — 基于 AI 的大学生职业规划智能体.md`
- 风格参考 PDF：`/home/runner/work/quote/quote/比赛用的最终ppt.pdf`

## 基础信息（已写入封面与页脚）

- 队伍名称：我们叫什么名字
- 所属学校：浙江师范大学
- 参赛赛道：A类

## 安装依赖

```bash
pip install -r requirements.txt
```

## 生成 PPTX

```bash
python tools/generate_ppt.py --output slides/competition.pptx
```

也可以指定 Markdown 输入模式：

```bash
python tools/generate_ppt.py --inputs "*.md" "docs/**/*.md" --output slides/competition.pptx
```

## 输出文件

- PPT 输出路径：`/home/runner/work/quote/quote/slides/competition.pptx`

## 风格说明

- 16:9 宽屏
- 灰白底色 + 冷蓝强调（背景 `#F5F7FA`，主色 `#2F6FED`）
- 默认字体：微软雅黑（Microsoft YaHei）
- 浅网格背景（形状绘制，无外部背景图依赖）
- 在技术栈/实现/部署/架构相关页面自动放置 Go 风格角标（右上角）
