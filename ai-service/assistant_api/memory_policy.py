import re
from typing import Literal

AnswerStyle = Literal["concise", "plain"]

STYLE_INSTRUCTIONS = {
    "concise": (
        "表达偏好：使用简洁表达，减少重复说明。"
        "必须完整保留必要的数字、否定词、适用条件和引用。"
        "不得为了简短删掉回答问题所必需的信息。"
    ),
    "plain": (
        "表达偏好：使用通俗语言，必要时简短解释术语。"
        "解释必须有本次资料支持，不得补充未经证实的事实。"
        "保留必要的数字、否定词、适用条件和引用。"
    ),
    # 仅供当前问题覆盖，不属于可以持久化的偏好枚举。
    "detailed": (
        "本次表达要求：在本次资料支持的范围内，详细解释相关条件和处理结果。"
        "不得补充未经证实的事实，保留必要的数字、否定词和引用。"
    ),
}

PREFERENCE_COMMANDS = {
    "以后回答简洁一点": ("set", "concise"),
    "以后请简洁回答": ("set", "concise"),
    "记住：以后回答简洁一点": ("set", "concise"),
    "以后请通俗解释": ("set", "plain"),
    "以后回答通俗一点": ("set", "plain"),
    "记住：以后请通俗解释": ("set", "plain"),
    "查看我的偏好": ("get", None),
    "忘记回答偏好": ("clear", None),
    "清除回答偏好": ("clear", None),
}


def preference_command(message):
    return PREFERENCE_COMMANDS.get(message.strip())


def effective_style(message, saved_style):
    patterns = [
        (
            r"^(?:这次|本次)?(?:请)?(?:简洁|简短|简要)"
            r"(?:回答|说明|解释)(?:一下|一点)?[：:，,]",
            "concise",
        ),
        (
            r"^(?:这次|本次)?(?:请)?通俗"
            r"(?:解释|回答|说明)(?:一下|一点)?[：:，,]",
            "plain",
        ),
        (
            r"^(?:这次|本次)?(?:请)?详细"
            r"(?:解释|回答|说明)(?:一下|一点)?[：:，,]",
            "detailed",
        ),
    ]
    for pattern, style in patterns:
        if re.match(pattern, message.strip()):
            return style
    return saved_style or "plain"
