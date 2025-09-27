from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.resolve()
# asset
TARGET_REGION = "jp"
MASTERDATA_BASE_URL = "https://raw.githubusercontent.com/"
ASSET_BASE_URL = f"https:///{TARGET_REGION}-assets/"

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
msa_white_lists = []

AES_KEY_BYTES =
AES_IV_BYTES =
