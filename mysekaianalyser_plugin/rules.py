from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent, MessageEvent

config = nonebot.get_driver().config
white_lists = config.msa_white_list or []

def is_reply_to_sekai_file() -> Rule:
    async def _check(event: Event) -> bool:
        if not isinstance(event, GroupMessageEvent) or not isinstance(event, MessageEvent):
            return False
        for seg in event.message:
            if seg.type != "reply":
                return False
            if seg.type == "file":
                file_name = seg.data.get("file_name", "")
                file_id = seg.data.get("file_id") or seg.data.get("id")
                file_url = seg.data.get("url")
                if file_name.endswith('.bin') and (file_id or file_url):
                    logger.info(f"【匹配成功】群{event.group_id} | 用户{event.user_id} | 文件{file_name}")
                    return True
        return False

    return Rule(_check)

def is_valid_user() -> Rule:
    async def _check(event: Event) -> bool:
        if white_lists and event.user_id not in white_lists:
            return False
        return True
    return Rule(_check)