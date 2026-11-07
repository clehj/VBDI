# VBDI

用 PySide6 + libmpv 写的桌面视频播放器，面向 Windows。

轻量、无广告、无捆绑。自带菜单、快捷键、拖放、最近打开、音量记忆、性能提示，全部基于一个 mpv 内核，开箱即用。

## 特性

- 内核：libmpv（GPU 渲染 + 硬件解码，1080p60 / 4K 都能播）
- 界面：PySide6（Qt 6），深色主题，无多余控件
- 支持格式：mp4 / mkv / avi / mov / webm / flv / ts / m4v，以及 mpv 能解的所有格式
- 拖放打开：把文件拖进窗口直接播放
- 最近打开：自动记录最近 10 个文件，菜单一键重播
- 快捷键：空格暂停、方向键快进/音量、F 全屏、M 静音
- 音量记忆：关闭时保存，下次启动恢复
- 更新检查：可选，通过远程 `version.txt` 提示新版本

## 依赖

- **Python**：3.10 或更高版本
- **PySide6**：`pip install PySide6`
- **python-mpv**：`pip install python-mpv`
- **libmpv-2.dll**：见下文，需要手动下载

## 快速开始

### 1. 安装 Python 依赖

```powershell
pip install PySide6 python-mpv
```

或使用 `requirements.txt`：

```powershell
pip install -r requirements.txt
```

### 2. 下载 libmpv

1. 打开 [shinchiro 的 mpv Windows 构建](https://github.com/shinchiro/mpv-winbuild-cmake/releases)
2. 找最新 release，下载 **`mpv-dev-x86_64-v3-*.7z`**
   - 如果 CPU 不支持 AVX2（较老的机器），改下 `mpv-dev-x86_64-*.7z`
3. 用 7-Zip 解压
4. 从解压目录里取出 **`libmpv-2.dll`**
5. 把 `libmpv-2.dll` 放到 **`player.py` 同目录**

目录结构应该是：

```
VBDI/
├── player.py
├── mpv_engine.py
├── libmpv-2.dll     ← 就放这里
├── ...
```

### 3. 运行

```powershell
python player.py
```

或带文件直接播放：

```powershell
python player.py "D:\Videos\movie.mp4"
```

首次启动会在同目录生成 `config.json`（配置）和 `player.log`（日志，默认关闭）。

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `Space` | 播放 / 暂停 |
| `←` / `→` | 快退 / 快进 5 秒 |
| `↑` / `↓` | 音量 +5 / -5 |
| `M` | 静音切换 |
| `F` | 全屏切换 |
| `Esc` | 退出全屏 |
| `Ctrl+O` | 打开文件 |
| `Ctrl+,` | 打开设置 |
| `Ctrl+Q` | 退出 |

## 配置文件

`config.json` 在 `player.py` 同目录，可以直接编辑，也可以走菜单「设置 → 首选项」。字段说明：

```jsonc
{
  "version": 1,
  "default_volume": 80,          // 启动时的默认音量 0-100
  "default_folder": "",          // 打开文件对话框的起始目录
  "window_width": 960,           // 窗口宽度，关闭时自动保存
  "window_height": 640,          // 窗口高度，关闭时自动保存
  "log_enabled": false,          // 是否写 player.log
  "check_update": true,          // 启动时是否检查新版本
  "decoder_preference": "auto",  // auto / software / hardware
  "recent_files": [],            // 最近打开列表，自动维护
  "max_recent": 10               // 最近打开列表长度上限
}
```

## 日志

默认关闭，日志文件不会生成。需要调试时：

1. 菜单「设置 → 首选项 → 高级 → 启用日志」勾选，重启程序
2. 或直接改 `config.json` 的 `"log_enabled": true`
3. 日志写入 `player.log`，每次启动覆盖

## 更新检查

默认关闭（`version.py` 中 `UPDATE_CHECK_URL` 为空）。要启用：

1. 在 GitHub / Gitee / 任意 HTTP 服务器托管一个 `version.txt`

```text
1.2.0
https://github.com/your-name/vbdi/releases/tag/v1.2.0
```

2. 修改 `version.py`：

```python
CURRENT_VERSION = "1.0.0"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/your-name/vbdi/main/version.txt"
```

3. 每次发版，同时更新 `CURRENT_VERSION` 和远程 `version.txt`

## 打包成 exe

```powershell
pip install pyinstaller

pyinstaller ^
  --onefile ^
  --windowed ^
  --name VBDI ^
  --add-binary "libmpv-2.dll;." ^
  --hidden-import mpv ^
  player.py
```

生成的 `dist\VBDI.exe` 是单文件绿色版，双击即可运行。

首次启动 5~10 秒（解压内置 DLL 到临时目录），之后正常。如果嫌慢，去掉 `--onefile` 改为 `--onedir`，会生成一个文件夹，启动几乎瞬时。

## 项目结构

```
VBDI/
├── player.py            # 主窗口、菜单、快捷键、进度条
├── mpv_engine.py        # libmpv 封装，实例复用
├── config.py            # 配置读写
├── settings_dialog.py   # 首选项对话框
├── log_setup.py         # 日志初始化
├── version.py           # 版本号、更新检查
├── requirements.txt
├── libmpv-2.dll         # 用户手动下载
├── config.json          # 运行时生成
└── player.log           # 运行时生成
```

## 已知限制

- **Windows 专用**。libmpv 在其他平台也有，但 `os.add_dll_directory` 和 `WA_NativeWindow` 的处理是 Windows 特化。Linux / macOS 需要小改。
- **不支持外挂字幕**。mpv 本身支持，本播放器暂未接入 UI。
- **不支持多音轨切换**。同上。
- 这些功能通过 mpv 的 API 很容易加，欢迎 PR。

## License

本项目基于 **GPLv3**。因为依赖的 libmpv 采用 GPLv2+，整个程序必须以 GPL 兼容协议发布。

也就是说：你可以自由使用、修改、分发、甚至商用，但**必须公开源代码**。

## 致谢

- [mpv](https://mpv.io/) / [libmpv](https://github.com/mpv-player/mpv)
- [python-mpv](https://github.com/jaseg/python-mpv)
- [PySide6](https://www.qt.io/qt-for-python)
- [PyAV](https://github.com/PyAV-Org/PyAV)（早期版本用，现已弃用）