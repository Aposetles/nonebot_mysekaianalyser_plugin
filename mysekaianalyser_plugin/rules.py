from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Event, MessageEvent, GroupMessageEvent

from .configs import msa_white_lists

white_lists = msa_white_lists

def is_valid_sekai_file() -> Rule:
    """
    一个规则检查器 (Rule)，用于判断消息是否包含一个有效的 .bin 文件。
    """
    async def _check(event: Event) -> bool:
        if not isinstance(event, MessageEvent):
            return False

        for seg in event.message:
            if seg.type == "file":
                file_name = seg.data.get("file", "") or seg.data.get("file_name", "")

                file_url = seg.data.get("url")

                if file_name.endswith('.bin') and file_url:

                    log_head = ""
                    if isinstance(event, GroupMessageEvent):
                        log_head = f"群聊 {event.group_id}"
                    else:
                        log_head = "私聊"

                    logger.info(f"【MySekai规则匹配成功】来源: {log_head} | 用户: {event.user_id} | 文件: {file_name}")
                    return True

        return False

    return Rule(_check)

def is_valid_user() -> Rule:
    """
    一个规则检查器 (Rule)，用于判断用户是否在白名单中。
    如果白名单为空，则对所有用户生效。
    """
    async def _check(event: Event) -> bool:

        if white_lists and event.get_user_id() in white_lists:
            logger.info(f"【MySekai白名单匹配成功】| 用户: {event.user_id}")
            return True

        return False

    return Rule(_check)