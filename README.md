# Competition PPTX Generator

本仓库提供脚本，可将仓库内 Markdown（按页总结内容）自动生成**浅色灰白、简约科技数码风**的 16:9 比赛 PPTX，并参考仓库 PDF 统一主题。

## 输入来源

- Markdown 内容源：`CareerPlanner — 基于 AI 的大学生职业规划智能体.md`
- 风格参考 PDF：`比赛用的最终ppt.pdf`
- Go Logo 资源：`assets/icons/go.png`
- 技术图标资源：`assets/icons/*.png`（Go/Docker/MySQL/Redis/Kubernetes/PostgreSQL/Nginx/GitHub）
- 科技背景素材：`assets/backgrounds/scene-*.jpg`（12 张）
- 素材来源与许可：`assets/ATTRIBUTION.md`

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

- 固定总页数策略：输出严格 `20` 页（封面 1 页 + 内容 19 页）
  - 结构固定为：1 封面、2 目录、3~18 内容、19 总结与展望、20 Q&A/感谢
  - 内容超出时：自动合并相邻小节并摘要（每页 3~5 条要点）
  - 内容不足时：自动补齐亮点/架构/技术栈/部署/演示流程等设计型页面
- 背景镶嵌：每页自动加载科技背景图，并叠加白色蒙层保持灰白干净基调
  - 支持三种背景构图轮换：右侧 35% 大图 / 全幅淡化背景 / 对角切片背景
- 右侧固定数码面板：统一放置技术 logo（最多 4 个）+ 标签 + 关键字，避免页面过空
- 统一主题组件：顶部强调条、标题分隔线、玻璃卡片（浅透白 + 冷灰蓝描边 + 轻阴影）、统一页脚与页码
- 轻量数码背景纹理：低对比 PCB 线条/点阵 + HUD 圆弧（章节页会稍增强）
- 多布局模板：Cover / Agenda / Section Divider / Content Left+Right Panel / Two-column Cards / Timeline
- 多布局自动选择：
  - Layout A（左文右图标区）
  - Layout B（双栏要点）
  - Layout C（章节/过渡页）
  - Layout D（流程/阶段页）
- 内容优化：
  - 要点超过阈值自动拆页并添加 `(1/2)` 标记
  - Markdown 表格渲染为卡片式两列对齐
  - Markdown 代码块渲染为深色代码卡片（等宽字体）
- 多技术图标规则：标题/要点命中关键词时自动放置对应 logo（Go/Docker/MySQL/Redis/K8s/PostgreSQL/Nginx/GitHub）
