"""配置的加载与保存。所有可调参数都持久化到 config.json。"""
import copy
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "hotkey_open": "v",
    "hotkey_dismiss": "esc",
    "groups": [],
    "display": {
        "position": "cursor",
        "size": 120,
        "duration": 2.5,
        "fade": True,
        "monitor": 0,
    },
    "wheel": {
        "radius": 130,
    },
}

# 显示位置允许的取值
POSITIONS = [
    "cursor",
    "center",
    "bottom-center",
    "top-center",
    "bottom-left",
    "bottom-right",
    "top-left",
    "top-right",
]

POSITION_LABELS = {
    "cursor": "跟随鼠标",
    "center": "屏幕中心",
    "bottom-center": "屏幕下方居中",
    "top-center": "屏幕上方居中",
    "bottom-left": "左下角",
    "bottom-right": "右下角",
    "top-left": "左上角",
    "top-right": "右上角",
}


def _merge(defaults, data):
    """用 data 覆盖 defaults，返回新字典；嵌套 dict 递归合并，保证新增字段有默认值。"""
    result = copy.deepcopy(defaults)
    if not isinstance(data, dict):
        return result
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _migrate(data):
    """把旧版配置升级到当前结构。

    旧版用平铺的 ``emotes`` 列表；现改为 ``groups``（每个分组含 name + emotes）。
    滚轮中心死区 ``inner_radius`` 已移除。
    """
    if not isinstance(data, dict):
        return data
    data = copy.deepcopy(data)
    if "groups" not in data and "emotes" in data:
        data["groups"] = [{"name": "默认", "emotes": data.pop("emotes")}]
    if isinstance(data.get("wheel"), dict):
        data["wheel"].pop("inner_radius", None)
    return data


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = _migrate(json.load(f))
            return _merge(DEFAULT_CONFIG, data)
        except (json.JSONDecodeError, OSError):
            pass
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
