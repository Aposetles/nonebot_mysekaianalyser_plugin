# mysekaianalyser_plugin/__init__.py
import os
import shutil  # 新增：用于文件复制
import tempfile
import subprocess
import asyncio
import re
import aiohttp
import importlib.util
from pathlib import Path
from nonebot.adapters.onebot.v11 import (
    Message, MessageSegment, Bot, Event,
    GroupMessageEvent, MessageEvent, ActionFailed
)
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, on_message

__plugin_meta__ = PluginMetadata(
    name="MySekai文件解析",
    description="接收群内.bin文件，自动解析并发送合并地图图+统计图",
    usage="群内发送mysekai.bin文件即可触发"
)

# 核心配置
PROJECT_ROOT = Path(r"C:\Users\Aposetles\Desktop\bot\cnmysekai\mysekaianalyser")
ALLOWED_SUFFIX = ".bin"
TIMEOUT = 300
# 只保留目标图片：合并地图图 + 统计图
TARGET_IMGS = [
    PROJECT_ROOT / "output_maps.png",  # 四张地图合并图
    PROJECT_ROOT / "output_summary.png"  # 统计图
]

# 路径合法性检查
if not PROJECT_ROOT.exists():
    logger.error(f"【错误】未找到mysekaianalyser项目！路径：{PROJECT_ROOT}")


# 工具函数
def is_module_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


async def download_file_from_url(url: str, save_path: Path) -> bool:
    """URL下载文件（仅日志，无群消息）"""
    if not url:
        logger.error("【URL下载】URL为空")
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    logger.error(f"【URL下载】状态码{resp.status}：{url[:50]}...")
                    return False
                with open(save_path, "wb") as f:
                    while True:
                        chunk = await resp.content.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
        file_size = os.path.getsize(save_path)
        if file_size < 100:
            logger.error(f"【URL下载】文件过小（{file_size}字节）")
            return False
        logger.info(f"【URL下载成功】{save_path}（{file_size // 1024}KB）")
        return True
    except Exception as e:
        logger.error(f"【URL下载出错】{str(e)}", exc_info=True)
        return False


async def run_python_script(script_path: Path, args: list, cwd: Path) -> int:
    """运行脚本（仅日志，无群消息）"""
    if not script_path.exists():
        logger.error(f"【脚本错误】{script_path}不存在")
        return -1
    cmd = ["python", str(script_path)] + args
    logger.debug(f"【脚本命令】{' '.join(cmd)} | 目录：{cwd}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        stdout = stdout_bytes.decode("gbk", errors="ignore") if stdout_bytes else ""
        stderr = stderr_bytes.decode("gbk", errors="ignore") if stderr_bytes else ""
        if stdout:
            logger.debug(f"【脚本输出】{script_path.name}：\n{stdout[:2000]}")
        if stderr:
            if "UnicodeEncodeError" in stderr and "gbk" in stderr:
                logger.warning(f"【脚本编码提示】{script_path.name}表情编码错误，不影响功能")
            logger.warning(f"【脚本警告】{script_path.name}：\n{stderr[:3000]}")
        return proc.returncode
    except asyncio.TimeoutError:
        proc.kill()
        logger.error(f"【脚本超时】{script_path.name}（{TIMEOUT}秒）")
        return -2
    except Exception as e:
        logger.error(f"【脚本出错】{script_path.name}：{str(e)}", exc_info=True)
        return -3


#  消息匹配规则
def is_valid_sekai_file() -> Rule:
    async def _check(event: Event) -> bool:
        if not isinstance(event, GroupMessageEvent) or not isinstance(event, MessageEvent):
            return False
        for seg in event.message:
            if seg.type == "file":
                file_name = seg.data.get("file_name", "")
                file_id = seg.data.get("file_id") or seg.data.get("id")
                file_url = seg.data.get("url")
                if file_name.endswith(ALLOWED_SUFFIX) and (file_id or file_url):
                    logger.info(f"【匹配成功】群{event.group_id} | 用户{event.user_id} | 文件{file_name}")
                    return True
        return False

    return Rule(_check)


# 核心处理函数
sekai_file_handler = on_message(rule=is_valid_sekai_file(), priority=5, block=True)


@sekai_file_handler.handle()
async def process_sekai_file(bot: Bot, event: GroupMessageEvent):
    try:
        # 1. 提取文件信息
        file_seg = next((seg for seg in event.message if
                         seg.type == "file" and seg.data.get("file_name", "").endswith(ALLOWED_SUFFIX)), None)
        if not file_seg:
            await sekai_file_handler.finish()  # 无文件，静默结束
            return

        file_name = file_seg.data.get("file_name", "mysekai.bin")
        file_url = file_seg.data.get("url")
        nickname = event.sender.nickname or "未知用户"
        await sekai_file_handler.send(f"收到@{nickname}的{file_name}，正在生成图片...")

        # 2. 下载文件
        with tempfile.TemporaryDirectory() as temp_dir:
            local_file = Path(temp_dir) / file_name
            download_success = False

            if file_url:
                download_success = await download_file_from_url(file_url, local_file)
            if not download_success:
                await sekai_file_handler.finish("文件下载失败，请重新上传")
                return

            # 新增：将临时文件复制到解密脚本目录，并重命名为mysekai.bin（适配解密脚本的硬编码）
            target_bin_path = PROJECT_ROOT / "mysekai.bin"
            try:
                shutil.copy2(local_file, target_bin_path)  # 复制文件（保留元数据）
                logger.info(f"【文件复制成功】{local_file} -> {target_bin_path}")
            except Exception as e:
                logger.error(f"【文件复制失败】{str(e)}")
                await sekai_file_handler.finish("文件处理失败，无法准备解密")
                return

            # 3. 解密文件（使用复制后的mysekai.bin路径）
            decrypt_script = PROJECT_ROOT / "decrypter.py"
            if not decrypt_script.exists():
                await sekai_file_handler.finish("解析依赖缺失，无法解密文件")
                return

            json_file = PROJECT_ROOT / "mysekai.json"
            # 修改：解密参数改为复制后的bin文件路径
            decrypt_result = await run_python_script(decrypt_script, [str(target_bin_path), str(json_file)],
                                                     PROJECT_ROOT)

            # 清理：无论解密成功与否，删除复制的bin文件
            if target_bin_path.exists():
                try:
                    os.remove(target_bin_path)
                    logger.info(f"【临时文件清理】已删除{target_bin_path}")
                except Exception as e:
                    logger.warning(f"【临时文件清理失败】{str(e)}")

            if decrypt_result != 0 or not (json_file.exists() and json_file.stat().st_size > 100):
                await sekai_file_handler.finish("文件解密失败，可能文件损坏")
                return

            # 4. 生成图片
            main_script = PROJECT_ROOT / "main.py"
            config_path = PROJECT_ROOT / "configs.py"
            original_config = None

            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    original_config = f.read()
                escaped_json = json_file.as_posix().replace("\\", "\\\\")
                new_config = re.sub(r'(INPUT_FILE\s*=\s*["\']).*?(["\'])', rf'\1{escaped_json}\2', original_config)
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(new_config)

            try:
                await run_python_script(main_script, [], PROJECT_ROOT)

                # 5. 发送目标图片
                valid_imgs = []
                for img_path in TARGET_IMGS:
                    if img_path.exists() and img_path.stat().st_size > 1000:
                        valid_imgs.append(img_path)
                        logger.info(f"【有效图片】{img_path.name}（{img_path.stat().st_size // 1024}KB）")

                if valid_imgs:
                    await sekai_file_handler.send("解析完成，生成图片如下：")
                    for img in valid_imgs:
                        await sekai_file_handler.send(MessageSegment.image(img))
                else:
                    await sekai_file_handler.finish("图片生成失败，未找到有效结果")

            finally:
                if original_config and config_path.exists():
                    with open(config_path, "w", encoding="utf-8") as f:
                        f.write(original_config)
                    logger.info("【恢复配置】已恢复configs.py")

    except Exception as e:
        error_msg = f"解析出错：{str(e)[:20]}..."
        logger.error(f"【解析异常】{error_msg}", exc_info=True)
        await sekai_file_handler.finish(error_msg)