import os
os.add_dll_directory(os.path.dirname(os.path.abspath(__file__)))

import logging
import threading
import mpv


logger = logging.getLogger("mpv")


class MpvEngine:
    """用 libmpv 内核播放。

    mpv 实例只创建一次，之后切换文件走 loadfile 命令。
    只有改解码方式才会重建实例。
    """

    def __init__(self, wid: int, decoder_preference: str = "auto"):
        self._wid = wid
        self._decoder_pref = decoder_preference
        self._current_path = None
        self._lock = threading.Lock()

        self._duration = 0.0
        self._position = 0.0
        self._paused = False
        self._ended = False
        self._seeking = False

        self._player = self._build_player()

    def _build_player(self) -> mpv.MPV:
        hwdec = "auto"
        if self._decoder_pref == "software":
            hwdec = "no"
        elif self._decoder_pref == "hardware":
            hwdec = "auto-safe"

        player = mpv.MPV(
            wid=str(self._wid),
            vo="gpu",
            hwdec=hwdec,
            keep_open="yes",
            osc=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            config=False,
            terminal=False,
        )

        player.observe_property("duration", self._on_duration)
        player.observe_property("time-pos", self._on_time_pos)
        player.observe_property("pause", self._on_pause)
        player.observe_property("eof-reached", self._on_eof)
        player.observe_property("seeking", self._on_seeking)
        return player

    # ── 属性回调（mpv 内部线程触发）────────
    def _on_duration(self, _name, value):
        with self._lock:
            self._duration = float(value) if value else 0.0

    def _on_time_pos(self, _name, value):
        with self._lock:
            self._position = float(value) if value else 0.0

    def _on_pause(self, _name, value):
        with self._lock:
            self._paused = bool(value)

    def _on_eof(self, _name, value):
        with self._lock:
            self._ended = bool(value)

    def _on_seeking(self, _name, value):
        with self._lock:
            self._seeking = bool(value)

    # ── 播放控制 ───────────────────────────
    def play(self, path: str):
        with self._lock:
            self._ended = False
            self._position = 0.0
            self._duration = 0.0

        if self._current_path is None:
            self._player.play(path)
        else:
            self._player.command("loadfile", path, "replace")
        self._current_path = path
        logger.info(f"mpv.load path={path}")

    def pause(self):
        self._player.pause = True

    def resume(self):
        self._player.pause = False

    def toggle_pause(self):
        self._player.pause = not self._player.pause

    def seek(self, seconds: float):
        self._player.command("seek", seconds, "absolute")

    def set_volume(self, v: float):
        self._player.volume = max(0.0, min(1.0, v)) * 100.0

    def set_mute(self, muted: bool):
        self._player.mute = bool(muted)

    def stop(self):
        try:
            self._player.command("stop")
        except Exception:
            pass
        self._current_path = None

    def set_decoder_preference(self, pref: str):
        if pref == self._decoder_pref:
            return
        logger.info(f"mpv.rebuild_decoder old={self._decoder_pref} new={pref}")
        old_path = self._current_path
        self._decoder_pref = pref
        try:
            self._player.terminate()
        except Exception:
            pass
        self._current_path = None
        self._player = self._build_player()
        if old_path:
            self.play(old_path)

    def terminate(self):
        try:
            self._player.terminate()
        except Exception:
            pass

    # ── 属性 ───────────────────────────────
    @property
    def position(self) -> float:
        with self._lock:
            return self._position

    @property
    def duration(self) -> float:
        with self._lock:
            return self._duration

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def ended(self) -> bool:
        with self._lock:
            return self._ended

    @property
    def seeking(self) -> bool:
        with self._lock:
            return self._seeking