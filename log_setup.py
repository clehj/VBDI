import logging
from pathlib import Path


LOG_FILE = "player.log"
LOG_FILE_LEVEL = "DEBUG"            # DEBUG / INFO / WARNING / ERROR
CONSOLE_LEVEL_WHEN_ON = logging.INFO
CONSOLE_LEVEL_WHEN_OFF = logging.WARNING

FILE_FORMAT = ("%(asctime)s.%(msecs)03d [%(levelname)-5s] "
               "%(name)-6s: %(message)s")
CONSOLE_FORMAT = "%(asctime)s [%(levelname)-5s] %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(enabled: bool = False):
    """配置 root logger。

    enabled=True : 写 player.log（级别按 LOG_FILE_LEVEL），控制台 INFO+
    enabled=False: 不写文件，控制台 WARNING+（保留错误提示）

    返回值：日志文件路径（启用时），或 None（关闭时）。
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT))

    if not enabled:
        root.setLevel(CONSOLE_LEVEL_WHEN_OFF)
        ch.setLevel(CONSOLE_LEVEL_WHEN_OFF)
        root.addHandler(ch)
        return None

    path = Path(LOG_FILE).resolve()
    file_level = getattr(logging, LOG_FILE_LEVEL.upper(), logging.DEBUG)

    root.setLevel(logging.DEBUG)

    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(fh)

    ch.setLevel(CONSOLE_LEVEL_WHEN_ON)
    root.addHandler(ch)
    return path