"""
test_evalscript.py — Standalone dev script for testing Sentinel Hub WMS evalscript.

STATUS: NOT PART OF THE PYTEST SUITE. Development/debugging only.

This script was used to verify Sentinel Hub WMS connectivity with a custom
evalscript.  It contains a hardcoded instance_id and empty OAuth credentials.
Run manually if needed; it is not executed by pytest.
"""
import sys
from sentinelhub import BBox, CRS, WmsRequest, MimeType, DataCollection, SHConfig, CustomUrlParam
import numpy as np

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "B11", "SCL"], units: "DN" }],
    output: { bands: 4, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  return [sample.B04 / 10000, sample.B08 / 10000, sample.B11 / 10000, sample.SCL];
}
"""

try:
    config = SHConfig()
    config.instance_id = '20cbcbb7-9d73-4642-b077-806f6efe493b'
    config.sh_client_id = ''
    config.sh_client_secret = ''
    
    req = WmsRequest(
        data_collection=DataCollection.SENTINEL2_L1C,
        layer='1_TRUE-COLOR-L1C',
        bbox=BBox([12.446, 41.874, 12.541, 41.917], crs=CRS.WGS84),
        time=('2023-01-01', '2023-02-01'),
        width=512,  # Increased to avoid SentinelHub limit with large bboxes
        height=512,
        maxcc=0.5,
        image_format=MimeType.TIFF,
        custom_url_params={CustomUrlParam.EVALSCRIPT: EVALSCRIPT},
        config=config
    )
    print('Testing WmsRequest with Evalscript...')
    data = req.get_data()
    print('Num frames:', len(data))
    if data:
        print('Frame shape:', data[0].shape)
        print('Dtype:', data[0].dtype)
except Exception as e:
    import traceback
    traceback.print_exc()
