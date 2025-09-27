import os
import json
import asyncio
from pathlib import Path
from typing import Set, Callable, Coroutine

import aiohttp
import aiofiles
from tqdm.asyncio import tqdm

from ..configs import RESOURCE_PATH, TARGET_REGION, MASTERDATA_BASE_URL, ASSET_BASE_URL

METADATA_FILES = [
    "mysekaiMaterials", "mysekaiPhenomenas", "mysekaiSiteHarvestFixtures",
    "gameCharacterUnits", "mysekaiGameCharacterUnitGroups", "mysekaiMusicRecords",
    "musics", "mysekaiItems", "mysekaiFixtures",
]

STATIC_FILES = [
    *[f"mysekai/gate_icon/gate_{i}.png" for i in range(1, 6)],
]

async def download_file(session: aiohttp.ClientSession, url: str, dest_path: Path) -> bool:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(dest_path, 'wb') as f:
                    await f.write(await response.read())
                return True
            return False
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return False

async def download_asset(session: aiohttp.ClientSession, path: str, dest_base: Path) -> bool:
    path_no_rip = path.replace("_rip", "")
    dest_path = dest_base / path_no_rip

    if dest_path.exists():
        return True # 已存在，跳过

    # 优先 ondemand
    url_ondemand = f"{ASSET_BASE_URL}ondemand/{path_no_rip}"
    if await download_file(session, url_ondemand, dest_path):
        return True

    # 失败则 startapp
    url_startapp = f"{ASSET_BASE_URL}startapp/{path_no_rip}"
    return await download_file(session, url_startapp, dest_path)

# --- 主更新函数 ---

ProgressCallback = Callable[[str], Coroutine[None, None, None]]

async def update_resources(progress_callback: ProgressCallback):
    """
    主更新函数，接收一个异步回调函数来报告进度。
    """
    metadata_dest_dir = RESOURCE_PATH / "metadata" / TARGET_REGION

    # --- 1. 下载 Metadata ---
    await progress_callback(f"阶段 1/3: 开始下载 {len(METADATA_FILES)} 个元数据文件...")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        tasks = []
        for table_name in METADATA_FILES:
            url = f"{MASTERDATA_BASE_URL}{table_name}.json"
            dest = metadata_dest_dir / f"{table_name}.json"
            tasks.append(download_file(session, url, dest))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
    await progress_callback(f"元数据下载完成，成功 {success_count}/{len(METADATA_FILES)} 个。")

    # --- 2. 提取动态资源路径 ---
    await progress_callback("阶段 2/3: 正在从元数据中提取资源路径...")

    asset_paths: Set[str] = set()
    static_paths: Set[str] = set()

    def load_json_table(filename):
        try:
            with open(metadata_dest_dir / filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: return []

    # (此处提取逻辑与您提供的代码完全相同，只是路径处理改为 Path 对象)
    for fixture in load_json_table("mysekaiSiteHarvestFixtures.json"):
        static_paths.add(f"mysekai/harvest_fixture_icon/{fixture['mysekaiSiteHarvestFixtureRarityType']}/{fixture['assetbundleName']}.png")
    for phenom in load_json_table("mysekaiPhenomenas.json"):
        asset_paths.add(f"mysekai/thumbnail/phenomena/{phenom['iconAssetbundleName']}.png")
        static_paths.add(f"mysekai/phenom_bg/{phenom['id']}.png")
    for mat in load_json_table("mysekaiMaterials.json"):
        asset_paths.add(f"mysekai/thumbnail/material/{mat['iconAssetbundleName']}.png")
    for item in load_json_table("mysekaiItems.json"):
        asset_paths.add(f"mysekai/thumbnail/item/{item['iconAssetbundleName']}.png")
    for fixture in load_json_table("mysekaiFixtures.json"):
        name = fixture['assetbundleName']
        for i in range(1, 7): asset_paths.add(f"mysekai/thumbnail/fixture/{name}_{i}.png")
    musics_map = {m['id']: m['assetbundleName'] for m in load_json_table("musics.json")}
    for record in load_json_table("mysekaiMusicRecords.json"):
        music_id = record.get('externalId')
        if music_id in musics_map: asset_paths.add(f"music/jacket/{musics_map[music_id]}/{musics_map[music_id]}.png")

    asset_paths.update({f"mysekai/site/sitemap/texture/{i}.png" for i in (5, 6, 7, 8)})
    asset_paths.update({f"thumbnail/material/{i}.png" for i in [17, 170, 173]})
    asset_paths.update({f"character/character_sd_l/chr_sp_{i}.png" for i in range(1, 41)})
    asset_paths.update({f"character/character_sd_l/chr_sp_{i}.png" for i in range(701, 741)})

    total_assets = len(asset_paths)
    total_statics = len(static_paths.union(STATIC_FILES))
    await progress_callback(f"提取完成: {total_assets} 个动态资源, {total_statics} 个静态资源。")

    # --- 3. 下载所有文件 ---
    await progress_callback(f"阶段 3/3: 开始下载共 {total_assets + total_statics} 个资源文件 (这可能需要几分钟)...")

    asset_dest_dir = RESOURCE_PATH / "assets" / TARGET_REGION
    static_dest_dir = RESOURCE_PATH / "static_images"

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        all_tasks = []
        for path in asset_paths:
            all_tasks.append(download_asset(session, path, asset_dest_dir))
        for path in static_paths.union(STATIC_FILES):
            all_tasks.append(download_asset(session, path, static_dest_dir))

        # 使用 tqdm 包装，但进度条只在控制台显示
        results = await tqdm.gather(*all_tasks, desc="Downloading Resources")
        success_count = sum(1 for r in results if r is True)

    await progress_callback(f"全部资源下载完成！\n成功: {success_count}/{len(all_tasks)} 个文件。")