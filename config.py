"""配置的加载与保存。所有可调参数都持久化到 config.json。"""
import copy
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "hotkey_open": "v",
    "hotkey_dismiss": "esc",
    "emotes": [],
    "display": {
        "position": "bottom-center",
        "size": 220,
        "duration": 2.5,
        "fade": True,
    },
    "wheel": {
        "radius": 130,
        "inner_radius": 45,
    },
}

# 显示位置允许的取值
POSITIONS = [
    "center",
    "bottom-center",
    "top-center",
    "bottom-left",
    "bottom-right",
    "top-left",
    "top-right",
]


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


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return _merge(DEFAULT_CONFIG, json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
