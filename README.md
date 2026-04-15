# Competition PPTX Generator

本仓库提供脚本，可将仓库内 Markdown（按页总结内容）自动生成**浅色灰白、简约科技数码风**的 16:9 比赛 PPTX，并参考仓库 PDF 统一主题。

## 输入来源

- Markdown 内容源：`CareerPlanner — 基于 AI 的大学生职业规划智能体.md`
- 风格参考 PDF：`比赛用的最终ppt.pdf`
- Go Logo 资源：`assets/icons/go.png`

## 固定信息（封面/页脚）

- 队伍名称：我们叫什么名字
- 所属学校：浙江师范大学
- 参赛赛道：A类

## 安装依赖

```bash
pip install -r requirements.txt
```

## 生成命令

```bash
python tools/generate_ppt.py \
  --inputs "CareerPlanner*.md" "docs/**/*.md" \
  --go-logo assets/icons/go.png \
  --output slides/competition.pptx
```

## 输出文件

- PPT 输出：`slides/competition.pptx`

## 生成特性（本次改造）

- 统一主题组件：顶部强调条、标题分隔线、玻璃卡片（浅透白 + 冷灰蓝描边 + 轻阴影）、统一页脚与页码
- 轻量数码背景纹理：低对比 PCB 线条/点阵 + HUD 圆弧（章节页会稍增强）
- 右侧装饰区：线框屏幕轮廓 + 冷蓝高光，保持克制且不抢正文
- 多布局自动选择：
  - Layout A（左文右图标区）
  - Layout B（双栏要点）
  - Layout C（章节/过渡页）
  - Layout D（流程/阶段页）
- 内容优化：
  - 要点超过阈值自动拆页并添加 `(1/2)` 标记
  - Markdown 表格渲染为卡片式两列对齐
  - Markdown 代码块渲染为深色代码卡片（等宽字体）
- Go 图标规则：标题/要点命中 `Go/golang/gin/grpc/编译/Go语言` 时自动放置 `assets/icons/go.png`
