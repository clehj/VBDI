from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QGroupBox, QSpinBox, QCheckBox, QLineEdit,
                               QPushButton, QDialogButtonBox, QFileDialog,
                               QLabel, QWidget, QComboBox)


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("首选项")
        self.setMinimumWidth(560)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(self._build_playback_group())
        root.addWidget(self._build_decoder_group())
        root.addWidget(self._build_ui_group())
        root.addWidget(self._build_advanced_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_playback_group(self) -> QGroupBox:
        group = QGroupBox("播放")
        form = QFormLayout(group)

        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(0, 100)
        self.volume_spin.setSuffix(" %")
        form.addRow("默认音量：", self.volume_spin)

        folder_row = QWidget()
        folder_layout = QHBoxLayout(folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("（留空则使用系统默认位置）")
        folder_layout.addWidget(self.folder_edit, 1)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)
        form.addRow("默认打开文件夹：", folder_row)

        return group

    def _build_decoder_group(self) -> QGroupBox:
        group = QGroupBox("解码")
        form = QFormLayout(group)

        self.decoder_combo = QComboBox()
        self.decoder_combo.addItem("自动（优先硬件）", "auto")
        self.decoder_combo.addItem("仅软件解码", "software")
        self.decoder_combo.addItem("仅硬件解码", "hardware")
        form.addRow("解码方式：", self.decoder_combo)

        hint = QLabel("切换解码方式会立即重建播放内核，当前视频自动续播")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", hint)

        return group

    def _build_ui_group(self) -> QGroupBox:
        group = QGroupBox("界面")
        form = QFormLayout(group)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(400, 3840)
        self.width_spin.setSuffix(" px")
        form.addRow("窗口宽度：", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(300, 2160)
        self.height_spin.setSuffix(" px")
        form.addRow("窗口高度：", self.height_spin)

        hint = QLabel("窗口尺寸修改在下次启动时生效")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", hint)

        return group

    def _build_advanced_group(self) -> QGroupBox:
        group = QGroupBox("高级")
        form = QFormLayout(group)

        self.log_check = QCheckBox("启用日志（写入 player.log）")
        form.addRow("", self.log_check)

        self.update_check = QCheckBox("启动时检查新版本")
        form.addRow("", self.update_check)

        return group

    def _load_values(self):
        self.volume_spin.setValue(int(self.config.get("default_volume")))
        self.folder_edit.setText(self.config.get("default_folder") or "")
        self.width_spin.setValue(int(self.config.get("window_width")))
        self.height_spin.setValue(int(self.config.get("window_height")))
        self.log_check.setChecked(bool(self.config.get("log_enabled")))
        self.update_check.setChecked(bool(self.config.get("check_update")))

        pref = self.config.get("decoder_preference")
        idx = self.decoder_combo.findData(pref)
        if idx >= 0:
            self.decoder_combo.setCurrentIndex(idx)

    def _browse_folder(self):
        start = self.folder_edit.text().strip() or ""
        folder = QFileDialog.getExistingDirectory(self, "选择默认文件夹", start)
        if folder:
            self.folder_edit.setText(folder)

    def _on_accept(self):
        folder = self.folder_edit.text().strip()
        if folder and not Path(folder).is_dir():
            folder = ""

        self.config.set("default_volume", int(self.volume_spin.value()))
        self.config.set("default_folder", folder)
        self.config.set("window_width", int(self.width_spin.value()))
        self.config.set("window_height", int(self.height_spin.value()))
        self.config.set("log_enabled", bool(self.log_check.isChecked()))
        self.config.set("check_update", bool(self.update_check.isChecked()))
        self.config.set("decoder_preference",
                        self.decoder_combo.currentData() or "auto")
        self.config.save()
        self.accept()