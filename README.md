# Emote Overlay

一个仿《杀戮尖塔 2》联机模式的屏幕表情 overlay：按快捷键在鼠标位置弹出径向表情滚轮，选中后表情在屏幕上弹出并淡出。专为直播 / 录屏设计，支持被 **OBS** 等软件带透明通道干净地捕捉。

## 功能

- 全局热键：**按住**呼出滚轮、**松开**选中并关闭（无需应用获得焦点）
- 径向滚轮：鼠标滑动高亮，松开呼出键选中
- 自定义表情：支持透明 **PNG**、动态 **GIF**、**WebP**，可上传 / 删除 / 重命名 / 排序
- 自定义快捷键（呼出键、关闭键）
- 表情弹出位置 / 大小 / 时长 / 淡入淡出可调
- 全屏透明置顶窗口，平时点击透传不影响其他操作
- 系统托盘图标，双击打开设置

## 环境要求

- Windows 10/11
- Python 3.11+

## 安装与运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

或者直接双击 `run.bat`（会自动创建虚拟环境并安装依赖）。

> 首次运行 `emotes/` 目录为空，滚轮会没有表情。可以先在托盘菜单打开「设置」上传表情，或运行
> `python scripts/gen_samples.py` 生成几个示例 emoji 表情用于测试。

## 使用

1. 托盘图标 → 双击（或右键 → 设置）打开设置面板。
2. 在「表情」里点「添加表情」上传自己的 PNG / GIF / WebP。
3. 在「快捷键」里点按钮后按下想要绑定的键（默认呼出 `V`，关闭 `Esc`）。
4. 回到游戏/桌面，**按住**呼出键（默认 `V`）→ 鼠标滑动到某个表情 → **松开**呼出键 → 表情弹出、滚轮关闭。松开时鼠标若停在中心死区则不选中。

## OBS 捕捉配置（重点）

要让 OBS 只把表情（带透明）合成到画面上，而不是一块带背景的窗口：

1. 先运行本程序（overlay 是透明的，OBS 需要它保持运行）。
2. 在 OBS 里添加来源 → **窗口采集（Window Capture）**。
3. 「窗口」下拉选择本程序窗口（标题通常为空 / 类名 `Qt`，选那个透明的窗口）。
4. **勾选「允许透明度（Allow transparency）」**。
5. 采集方式建议选「Windows 10 (1903 及更新)」或「位图（BitBlt）」。
6. 把该来源放在游戏/桌面画面来源的**上层**，即可透明叠加。

> 如果 OBS 里选不到窗口，可以先让 overlay 显示一次表情再刷新窗口列表，或用「按类名/标题匹配」。

## 已知限制

- **独占全屏**游戏（Exclusive Fullscreen）会盖过一切桌面 overlay，包括本程序。请把游戏设为**无边框窗口（Borderless）**模式，这也是 Discord / Steam overlay 的通用要求。
- 全局热键可能与某些游戏或软件冲突，可在设置里换键。
- 删除表情仅从列表移除，不删除 `emotes/` 里的文件，可手动清理。

## 项目结构

```
emote-overlay/
├── main.py             # 入口：overlay + 热键 + 托盘
├── overlay.py          # 透明置顶窗口、点击透传、滚轮/表情管理
├── hotkey.py           # 全局热键（keyboard 库）
├── wheel.py            # 径向表情滚轮
├── emote.py            # 表情弹出 + 动画
├── settings_dialog.py  # 设置面板
├── emote_manager.py    # 表情文件导入
├── config.py           # 配置读写
├── config.json         # 配置（运行时生成/更新）
├── emotes/             # 表情文件
├── scripts/            # 工具脚本
│   ├── gen_samples.py  # 生成示例表情
│   └── smoke_test.py   # 离线冒烟测试
└── requirements.txt
```
