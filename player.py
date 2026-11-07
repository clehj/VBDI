import sys
import threading
import logging
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QLabel, QSizePolicy,
                               QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QSlider, QMessageBox, QFileDialog,
                               QDialog)
from PySide6.QtGui import QDesktopServices, QAction, QKeySequence
from PySide6.QtCore import QTimer, Qt, QUrl

from log_setup import setup_logging
from config import Config
from settings_dialog import SettingsDialog
from mpv_engine import MpvEngine
import version as version_mod


logger = logging.getLogger("player")


VIDEO_FILTER = ("视频文件 (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.ts *.m4v);;"
                "所有文件 (*.*)")

WELCOME_TEXT = ("将视频文件拖放到这里\n\n"
                "或通过菜单　文件 → 打开文件（Ctrl+O）\n"
                "或从　文件 → 最近打开　中选择")

SEEK_STEP_S = 5.0
VOLUME_STEP = 5
LOAD_CHECK_MS = 3000


def format_time(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


class UpdateChecker:
    def __init__(self):
        self.result = None
        self.done = False

    def start(self):
        threading.Thread(target=self._run, daemon=True,
                         name="update_check").start()

    def _run(self):
        try:
            self.result = version_mod.check_latest()
        except Exception:
            self.result = None
        finally:
            self.done = True


def _show_update_dialog(parent, remote_version: str, download_url: str):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("发现新版本")
    box.setText(f"新版本 {remote_version} 可用")
    box.setInformativeText(
        f"当前版本：{version_mod.CURRENT_VERSION}\n是否前往下载？")
    go_btn = box.addButton("前往下载", QMessageBox.ButtonRole.AcceptRole)
    later_btn = box.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(go_btn)
    box.setEscapeButton(later_btn)
    box.exec()
    if box.clickedButton() is go_btn:
        QDesktopServices.openUrl(QUrl(download_url))


class PlayerWindow(QMainWindow):
    UI_TICK_MS = 200
    SLIDER_RESOLUTION = 1000

    def __init__(self, path: str = None, config: Config = None):
        super().__init__()
        self.config = config
        self.engine = None
        self._slider_dragging = False
        self._pending_seek_value = 0
        self._last_ended_shown = False
        self._load_gen = 0
        self._muted = False
        self._volume_before_mute = int(config.get("default_volume"))

        self._build_ui()
        self._build_menu()
        self._create_timer()
        self.setAcceptDrops(True)

        if path:
            self._switch_to_file(path)
        else:
            self._show_welcome()

    # ── UI 构建 ───────────────────────────
    def _build_ui(self):
        self.setWindowTitle("我的播放器")
        self.resize(int(self.config.get("window_width")),
                    int(self.config.get("window_height")))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        video_area = QWidget()
        video_area.setStyleSheet("background: black;")
        video_area.setMinimumSize(1, 1)
        video_area.setSizePolicy(QSizePolicy.Policy.Ignored,
                                 QSizePolicy.Policy.Ignored)
        grid = QGridLayout(video_area)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # mpv 渲染接收区
        self.mpv_widget = QWidget()
        self.mpv_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.mpv_widget.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
        self.mpv_widget.setMinimumSize(1, 1)
        self.mpv_widget.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Ignored)
        self.mpv_widget.hide()
        grid.addWidget(self.mpv_widget, 0, 0)

        # 欢迎页（和 mpv 同格重叠）
        self.welcome_label = QLabel(WELCOME_TEXT)
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setStyleSheet(
            "background: black; color: #888; font-size: 18px;")
        self.welcome_label.setMinimumSize(1, 1)
        self.welcome_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                         QSizePolicy.Policy.Ignored)
        grid.addWidget(self.welcome_label, 0, 0)

        root.addWidget(video_area, 1)
        root.addWidget(self._make_control_bar())

    def _make_control_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: #222;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)

        self.play_btn = QPushButton("⏸")
        self.play_btn.setFixedWidth(48)
        self.play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_btn.clicked.connect(self.toggle_pause)
        layout.addWidget(self.play_btn)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: white;")
        layout.addWidget(self.time_label)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, self.SLIDER_RESOLUTION)
        self.progress_slider.valueChanged.connect(self.on_slider_value_changed)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        layout.addWidget(self.progress_slider, 1)

        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setFixedWidth(32)
        self.volume_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume_btn.setStyleSheet(
            "background: transparent; border: none; color: white;")
        self.volume_btn.clicked.connect(self.toggle_mute)
        layout.addWidget(self.volume_btn)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.config.get("default_volume")))
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        layout.addWidget(self.volume_slider)
        return bar

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        act_open = QAction("打开文件…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self.action_open_file)
        file_menu.addAction(act_open)

        self.recent_menu = file_menu.addMenu("最近打开")
        self._refresh_recent_menu()

        file_menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        settings_menu = menubar.addMenu("设置(&S)")
        act_pref = QAction("首选项…", self)
        act_pref.setShortcut("Ctrl+,")
        act_pref.triggered.connect(self.action_open_settings)
        settings_menu.addAction(act_pref)

        help_menu = menubar.addMenu("帮助(&H)")
        act_update = QAction("检查更新", self)
        act_update.triggered.connect(self.action_check_update)
        help_menu.addAction(act_update)
        act_about = QAction("关于", self)
        act_about.triggered.connect(self.action_about)
        help_menu.addAction(act_about)

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        recent = self.config.get("recent_files") or []
        if not recent:
            act = QAction("（无最近文件）", self)
            act.setEnabled(False)
            self.recent_menu.addAction(act)
            return
        for path in recent:
            act = QAction(Path(path).name, self)
            act.setToolTip(path)
            act.triggered.connect(lambda checked=False, p=path: self._open_recent(p))
            self.recent_menu.addAction(act)
        self.recent_menu.addSeparator()
        act_clear = QAction("清空列表", self)
        act_clear.triggered.connect(self._clear_recent)
        self.recent_menu.addAction(act_clear)

    def action_open_file(self):
        start = self.config.get("default_folder") or ""
        path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", start, VIDEO_FILTER)
        if path:
            self._switch_to_file(path)

    def _open_recent(self, path: str):
        if not Path(path).is_file():
            QMessageBox.warning(self, "文件不存在",
                                f"找不到文件：\n{path}\n\n是否从最近打开中移除？")
            recent = list(self.config.get("recent_files") or [])
            if path in recent:
                recent.remove(path)
                self.config.set("recent_files", recent)
                self.config.save()
                self._refresh_recent_menu()
            return
        self._switch_to_file(path)

    def _clear_recent(self):
        self.config.clear_recent()
        self._refresh_recent_menu()

    # ── 文件切换（复用 mpv 实例）──────────
    def _switch_to_file(self, path: str):
        if not Path(path).is_file():
            QMessageBox.warning(self, "无法打开", f"文件不存在：\n{path}")
            return

        logger.info(f"switch_file path={path}")
        self._load_gen += 1
        gen = self._load_gen

        self._slider_dragging = False
        self._pending_seek_value = 0
        self._last_ended_shown = False

        self.welcome_label.hide()
        self.mpv_widget.show()
        self.setWindowTitle(f"我的播放器 - {Path(path).name}")

        if self.engine is None:
            pref = self.config.get("decoder_preference") or "auto"
            self.engine = MpvEngine(int(self.mpv_widget.winId()),
                                    decoder_preference=pref)
            self.engine.set_volume(self.volume_slider.value() / 100.0)

        self.engine.play(path)
        self.config.add_recent(path)
        self._refresh_recent_menu()

        self.play_btn.setEnabled(True)
        self.play_btn.setText("⏸")
        self.ui_timer.start()

        QTimer.singleShot(LOAD_CHECK_MS, lambda: self._check_load(gen, path))

    def _check_load(self, gen: int, path: str):
        if gen != self._load_gen:
            return
        if self.engine is None:
            return
        if self.engine.duration > 0:
            return
        logger.warning(f"load_failed path={path}")
        QMessageBox.warning(self, "无法播放",
                            f"该文件无法播放：\n{Path(path).name}\n\n"
                            f"可能不是有效的视频文件，或格式不受支持。")
        self.engine.stop()
        self._show_welcome()

    # ── 欢迎页 ─────────────────────────────
    def _show_welcome(self):
        self._slider_dragging = False
        self._pending_seek_value = 0
        self._last_ended_shown = False
        self.mpv_widget.hide()
        self.welcome_label.show()
        self.welcome_label.raise_()
        self.setWindowTitle("我的播放器")
        self.play_btn.setEnabled(False)
        self.play_btn.setText("▶")
        self.time_label.setText("00:00 / 00:00")
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(0)
        self.progress_slider.blockSignals(False)
        self.ui_timer.stop()

    # ── 播放控制 ───────────────────────────
    def toggle_pause(self):
        if self.engine is None:
            return
        if self.engine.ended:
            self.engine.seek(0)
            self.engine.resume()
            self._last_ended_shown = False
            self.play_btn.setText("⏸")
            return
        self.engine.toggle_pause()
        self.play_btn.setText("▶" if self.engine.paused else "⏸")

    def toggle_mute(self):
        if self.engine is None:
            return
        self._muted = not self._muted
        if self._muted:
            self._volume_before_mute = self.volume_slider.value()
            self.engine.set_mute(True)
            self.volume_btn.setText("🔇")
        else:
            self.engine.set_mute(False)
            self.volume_btn.setText("🔊")
            if self.volume_slider.value() == 0 and self._volume_before_mute > 0:
                self.volume_slider.setValue(self._volume_before_mute)

    def on_volume_changed(self, v: int):
        if v > 0 and self._muted:
            self._muted = False
            if self.engine is not None:
                self.engine.set_mute(False)
        if self.engine is not None:
            self.engine.set_volume(v / 100.0)
        self.volume_btn.setText(
            "🔊" if (v > 0 and not self._muted) else "🔇")

    # ── 进度条 ─────────────────────────────
    def on_slider_value_changed(self, value: int):
        self._slider_dragging = True
        self._pending_seek_value = value
        if self.engine and self.engine.duration > 0:
            pos = value / self.SLIDER_RESOLUTION * self.engine.duration
            self.time_label.setText(
                f"{format_time(pos)} / {format_time(self.engine.duration)}")

    def on_slider_released(self):
        self._slider_dragging = False
        if self.engine is None or self.engine.duration <= 0:
            return
        target = (self._pending_seek_value / self.SLIDER_RESOLUTION
                  * self.engine.duration)
        self.engine.seek(target)

    def _seek_relative(self, delta: float):
        if self.engine is None:
            return
        pos = self.engine.position + delta
        dur = self.engine.duration
        if dur > 0:
            pos = max(0.0, min(dur, pos))
        self.engine.seek(pos)

    # ── UI 刷新定时器 ──────────────────────
    def _create_timer(self):
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)

    def _update_ui(self):
        if self.engine is None:
            return

        if self.engine.ended and not self._last_ended_shown:
            self._last_ended_shown = True
            self.play_btn.setText("▶")
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(self.SLIDER_RESOLUTION)
            self.progress_slider.blockSignals(False)
            if self.engine.duration > 0:
                self.time_label.setText(
                    f"{format_time(self.engine.duration)} / "
                    f"{format_time(self.engine.duration)}")
            return

        if self.engine.ended or self._slider_dragging or self.engine.seeking:
            return

        pos = self.engine.position
        dur = self.engine.duration
        if dur > 0:
            self.time_label.setText(f"{format_time(pos)} / {format_time(dur)}")
            value = int(pos / dur * self.SLIDER_RESOLUTION)
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(max(0, min(self.SLIDER_RESOLUTION, value)))
            self.progress_slider.blockSignals(False)

    # ── 拖放 ───────────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if Path(path).is_file():
                event.acceptProposedAction()
                self._switch_to_file(path)
                return
        event.ignore()

    # ── 设置 / 更新 / 关于 ─────────────────
    def action_open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(int(self.config.get("default_volume")))
            self.volume_slider.blockSignals(False)
            if self.engine:
                self.engine.set_volume(self.volume_slider.value() / 100.0)
                pref = self.config.get("decoder_preference") or "auto"
                self.engine.set_decoder_preference(pref)

    def action_check_update(self):
        checker = UpdateChecker()
        checker.start()
        poll = QTimer(self)
        poll.setInterval(150)

        def _poll():
            if not checker.done:
                return
            poll.stop()
            if checker.result is None:
                QMessageBox.information(self, "检查更新", "已是最新版本。")
            else:
                remote, url = checker.result
                _show_update_dialog(self, remote, url)

        poll.timeout.connect(_poll)
        poll.start()

    def action_about(self):
        QMessageBox.about(self, "关于",
                          f"<b>我的播放器</b><br>"
                          f"版本 {version_mod.CURRENT_VERSION}<br><br>"
                          f"内核：libmpv<br>")

    # ── 键盘快捷键 ─────────────────────────
    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Space:
            self.toggle_pause()
        elif k == Qt.Key.Key_Left:
            self._seek_relative(-SEEK_STEP_S)
        elif k == Qt.Key.Key_Right:
            self._seek_relative(SEEK_STEP_S)
        elif k == Qt.Key.Key_Up:
            self.volume_slider.setValue(
                min(100, self.volume_slider.value() + VOLUME_STEP))
        elif k == Qt.Key.Key_Down:
            self.volume_slider.setValue(
                max(0, self.volume_slider.value() - VOLUME_STEP))
        elif k == Qt.Key.Key_M:
            self.toggle_mute()
        elif k == Qt.Key.Key_F:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif k == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    # ── 退出 ───────────────────────────────
    def closeEvent(self, event):
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())
        self.config.set("default_volume", self.volume_slider.value())
        self.config.save()
        self.ui_timer.stop()
        if self.engine is not None:
            self.engine.terminate()
            self.engine = None
        super().closeEvent(event)


def _start_update_check(win: PlayerWindow):
    if not win.config.get("check_update"):
        return
    checker = UpdateChecker()
    checker.start()
    poll = QTimer(win)
    poll.setInterval(150)

    def _poll():
        if not checker.done:
            return
        poll.stop()
        if checker.result is None:
            return
        remote, url = checker.result
        _show_update_dialog(win, remote, url)

    poll.timeout.connect(_poll)
    poll.start()


if __name__ == "__main__":
    config = Config()
    log_path = setup_logging(enabled=bool(config.get("log_enabled")))
    if log_path is not None:
        logger.info(f"log_file={log_path}")

    app = QApplication(sys.argv)
    path = sys.argv[1] if len(sys.argv) >= 2 else None
    win = PlayerWindow(path, config)
    win.show()
    _start_update_check(win)
    sys.exit(app.exec())