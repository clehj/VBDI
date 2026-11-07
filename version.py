import logging
import urllib.request


logger = logging.getLogger("version")


# ═══════════════════════════════════════════════
#  你的播放器当前版本号。每次发布新版要手动改这里，
#  同时把远程 version.txt 也改成同一个数字。
# ═══════════════════════════════════════════════
CURRENT_VERSION = "1.0.0"


# ═══════════════════════════════════════════════
#  远程版本文件地址。留空则关闭更新检查。
#
#  文件内容格式（两行）：
#    1.2.0
#    https://github.com/你的用户名/vbdi/releases/tag/v1.2.0
#
#  托管方式任选一种：
#  1. GitHub raw：
#     https://raw.githubusercontent.com/用户名/仓库/main/version.txt
#  2. Gitee raw：
#     https://gitee.com/用户名/仓库/raw/main/version.txt
#  3. jsDelivr CDN（套一层 GitHub）：
#     https://cdn.jsdelivr.net/gh/用户名/仓库@main/version.txt
#  4. 自建 HTTP 服务器
# ═══════════════════════════════════════════════
UPDATE_CHECK_URL = ""


# 网络请求超时（秒）。太长会拖慢启动，太短会误报失败。
UPDATE_TIMEOUT = 5.0


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("vV").split("."))
    except ValueError:
        return (0,)


def is_newer(remote: str, local: str) -> bool:
    r = _parse_version(remote)
    l = _parse_version(local)
    n = max(len(r), len(l))
    r = r + (0,) * (n - len(r))
    l = l + (0,) * (n - len(l))
    return r > l


def check_latest():
    """检查远程版本。

    返回 (remote_version, download_url)：有新版本
    返回 None：无新版本 / 未配置 URL / 网络失败 / 文件格式不对
    """
    if not UPDATE_CHECK_URL:
        return None

    try:
        with urllib.request.urlopen(UPDATE_CHECK_URL,
                                    timeout=UPDATE_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.info(f"update.check_failed: {e}")
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        logger.info("update.empty_response")
        return None

    remote = lines[0]
    download_url = lines[1] if len(lines) > 1 else UPDATE_CHECK_URL

    logger.info(f"update.check remote={remote} local={CURRENT_VERSION}")
    if is_newer(remote, CURRENT_VERSION):
        return remote, download_url
    return None