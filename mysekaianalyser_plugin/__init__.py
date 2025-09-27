import asyncio
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import orjson
import aiohttp
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot import require, on_message, on_command
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    Message,
    MessageSegment,
    GroupMessageEvent,
    # 删除了这里的 FileSegment 导入
)

# 导入本地模块
from .rules import is_valid_sekai_file, is_valid_user
from .configs import (TEMP_PATH, RESOURCE_PATH, TARGET_REGION, SHOW_HARVESTED, AES_KEY_BYTES, AES_IV_BYTES)
# --- 导入解密函数 ---
from .utils.decrypter import decrypt_and_parse_bin_file
# --------------------------
from .utils.loader import LocalAssetLoader
from .utils.asset_updator import update_resources
from .utils.drawer import combine_and_save_maps, draw_summary_image
from .utils.extractor import extract_all_harvest_map_data, extract_summary_data

__plugin_meta__ = PluginMetadata(
    name="MySekai文件解析",
    description="回复.bin文件消息以触发解析，生成统计图和地图，并以单条消息回复。",
    usage="在群聊中，回复某条包含 mysekai.bin 文件的消息即可触发。"
)

TEMP_PATH.mkdir(exist_ok=True)

async def download_file(url: str, save_path: Path) -> bool:
    """文件下载"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status == 200:
                    with open(save_path, "wb") as f:
                        f.write(await response.read())
                    return True
                logger.error(f"文件下载失败，状态码: {response.status}, URL: {url}")
                return False
    except Exception as e:
        logger.error(f"文件下载异常: {e}", exc_info=True)
        return False

def generate_images_sync(json_path: Path, output_summary_path: Path, output_maps_path: Path):
    """"图片生成"""
    start_time = datetime.now()
    logger.info(f"图片生成开始: {json_path.name}")
    loader = LocalAssetLoader(resource_path=RESOURCE_PATH, region=TARGET_REGION)
    with open(json_path, "r", encoding="utf-8") as f:
        mysekai_data = orjson.loads(f.read()) # 使用 orjson 加载更快
    summary_data = extract_summary_data(mysekai_data, loader, SHOW_HARVESTED)
    map_data_list = extract_all_harvest_map_data(mysekai_data, loader, SHOW_HARVESTED)
    summary_image = draw_summary_image(summary_data, loader)
    summary_image.save(output_summary_path)
    combine_and_save_maps(map_data_list, loader, output_maps_path)
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"图片生成完毕，耗时 {duration:.2f} 秒")


sekai_handler = on_message(rule=is_valid_user() & is_valid_sekai_file(), priority=1, block=False)

@sekai_handler.handle()
async def handle_sekai_file(bot: Bot, event: GroupMessageEvent):

    start_time = datetime.now()
    file_seg = next(
        (
            seg for seg in event.message
            if seg.type == "file" and seg.data.get("file", "").endswith(".bin")
        ),
        None
    )

    if not file_seg:
        return

    file_name = file_seg.data.get("file")
    file_url = file_seg.data.get("url")

    if not file_url:
        await sekai_handler.finish("无法获取文件下载链接。", reply_message=True)

    unique_seed = f"{event.user_id}-{file_name}-{datetime.now().timestamp()}"
    task_hash = hashlib.sha1(unique_seed.encode()).hexdigest()[:10]
    task_dir = TEMP_PATH / task_hash
    task_dir.mkdir(exist_ok=True)

    local_bin_path = task_dir / file_name
    decrypted_json_path = task_dir / "mysekai.json"
    output_summary_path = task_dir / "summary.png"
    output_maps_path = task_dir / "maps.png"

    try:
        sekai_handler.block = True
        await bot.send(event=event, message="收到，正在为您解析 MySekai 文件...", reply_message=True)

        if not await download_file(file_url, local_bin_path):
            await bot.send(event=event, message="文件下载失败，请稍后再试。", reply_message=True)
            return

        try:
            encrypted_bytes = local_bin_path.read_bytes()

            logger.info(f"开始解密文件: {file_name}")
            decrypted_data = await decrypt_and_parse_bin_file(encrypted_bytes, AES_KEY_BYTES, AES_IV_BYTES)

            with open(decrypted_json_path, "wb") as f:
                f.write(orjson.dumps(decrypted_data, option=orjson.OPT_INDENT_2))
            logger.info(f"文件解密成功 -> {decrypted_json_path}")

        except Exception as e:
            logger.error(f"文件解密失败 for {file_name}: {e}", exc_info=True)
            await bot.send(event=event, message="文件解密失败，可能是文件损坏、格式不正确或密钥错误。", reply_message=True)
            return

        await asyncio.to_thread(
            generate_images_sync,
            decrypted_json_path,
            output_summary_path,
            output_maps_path
        )

        result_message = Message()
        if output_summary_path.exists() and output_summary_path.stat().st_size > 1000:
            result_message.append(MessageSegment.image(output_summary_path))
        if output_maps_path.exists() and output_maps_path.stat().st_size > 1000:
            result_message.append(MessageSegment.image(output_maps_path))

        if result_message:
            duration = (datetime.now() - start_time).total_seconds()
            await bot.send(event=event, message=Message(f"解析完成！\n耗时 {duration:.2f} 秒\n" + result_message), reply_message=True)
        else:
            await bot.send(event=event, message="图片生成失败，未找到有效结果。", reply_message=True)

    except Exception as e:
        logger.error(f"处理 MySekai 文件时发生未知异常: {e}", exc_info=True)
        await bot.send(event=event, message="处理时发生内部错误，请联系管理员。", reply_message=True)
    finally:
        sekai_handler.block = False
        if task_dir.exists():
            shutil.rmtree(task_dir)
            logger.info(f"已清理临时目录: {task_dir}")

update_handler = on_command(
    "update_ms",
    rule=is_valid_user(),
    priority=2,
    block=True
)

@update_handler.handle()
async def handle_update_resources(bot: Bot, event: MessageEvent):
    msg_id = None

    async def progress_callback(text: str):
        nonlocal msg_id
        if msg_id is None:
            result = await update_handler.send(f"【MySekai资源更新】\n{text}")
            msg_id = result.get("message_id")
        else:
            try:
                await bot.delete_msg(message_id=msg_id)
            except Exception:
                pass
            result = await update_handler.send(f"【MySekai资源更新】\n{text}")
            msg_id = result.get("message_id")

    try:
        await update_resources(progress_callback)
    except Exception as e:
        logger.error(f"资源更新时发生未知错误: {e}", exc_info=True)
        await progress_callback(f"更新过程中发生严重错误，请检查后台日志。\n错误: {e}")