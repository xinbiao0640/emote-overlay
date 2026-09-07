"""表情文件的导入与管理：把用户选择的图片复制到 emotes/ 目录。"""
import os
import shutil

EMOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emotes")
ALLOWED_EXTS = {".png", ".gif", ".webp"}


def ensure_emotes_dir():
    os.makedirs(EMOTES_DIR, exist_ok=True)
    return EMOTES_DIR


def import_emote(src_path):
    """把外部图片复制进 emotes/ 目录，返回表情 dict。重名自动加序号。"""
    ensure_emotes_dir()
    ext = os.path.splitext(src_path)[1].lower()
    base = os.path.splitext(os.path.basename(src_path))[0] or "emote"
    # 安全化文件名（去掉路径分隔符等）
    base = "".join(c for c in base if c not in '\\/:*?"<>|').strip() or "emote"

    dest_name = f"{base}{ext}"
    dest_path = os.path.join(EMOTES_DIR, dest_name)
    counter = 1
    while os.path.exists(dest_path):
        dest_name = f"{base}_{counter}{ext}"
        dest_path = os.path.join(EMOTES_DIR, dest_name)
        counter += 1

    shutil.copyfile(src_path, dest_path)
    rel = os.path.relpath(dest_path, os.path.dirname(os.path.abspath(__file__)))
    return {"name": base, "file": rel.replace(os.sep, "/")}
