from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.resolve()
# asset
TARGET_REGION = "jp"
MASTERDATA_BASE_URL = "https://raw.githubusercontent.com/Sekai-World/sekai-master-db-diff/main/"
ASSET_BASE_URL = f"https://sekai-assets-bdf29c81.seiunx.net/{TARGET_REGION}-assets/"

# fonts
DEFAULT_FONT_PATH = PLUGIN_ROOT  / "resources/fonts/SourceHanSansSC-Regular.otf"
DEFAULT_BOLD_FONT_PATH = PLUGIN_ROOT / "resources/fonts/SourceHanSansSC-Bold.otf"
DEFAULT_HEAVY_FONT_PATH = PLUGIN_ROOT / "resources/fonts/SourceHanSansSC-Heavy.otf"

# main
INPUT_FILE = PLUGIN_ROOT / "mysekai.json"
TARGET_REGION = "jp"
SHOW_HARVESTED = True
OUTPUT_SUMMARY_FILENAME = "output_summary.png"
OUTPUT_MAPS_FILENAME = "output_maps.png"

ENABLE_MAP_CROPPING = True


RESOURCE_PATH = PLUGIN_ROOT / "resources"
TIMEOUT = 300
TEMP_PATH = PLUGIN_ROOT / "temp"
msa_white_lists = ['1597980590']

AES_KEY_BYTES = bytearray([103, 50, 102, 99, 67, 48, 90, 99, 122, 78, 57, 77, 84, 74, 54, 49])
AES_IV_BYTES = bytearray([109, 115, 120, 51, 73, 86, 48, 105, 57, 88, 69, 53, 117, 89, 90, 49])
