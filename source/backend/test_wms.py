"""
test_wms.py — Standalone dev script for testing Sentinel Hub WMS connectivity.

STATUS: NOT PART OF THE PYTEST SUITE. Development/debugging only.

This script was used to verify basic WMS request connectivity via Sentinel Hub.
It contains a hardcoded instance_id and empty OAuth credentials.
Run manually if needed; it is not executed by pytest.
"""
import sys
from sentinelhub import BBox, CRS, WmsRequest, MimeType, DataCollection, SHConfig

try:
    config = SHConfig()
    config.instance_id = '20cbcbb7-9d73-4642-b077-806f6efe493b'
    config.sh_client_id = ''  # Ensure no oauth happens if just using instance_id, though OGC might be deprecated.
    config.sh_client_secret = ''
    
    req = WmsRequest(
        data_collection=DataCollection.SENTINEL2_L1C,
        layer='1_TRUE-COLOR-L1C',
        bbox=BBox([12.446, 41.874, 12.541, 41.917], crs=CRS.WGS84),
        time=('2023-01-01', '2023-02-28'),
        width=512,
        height=512,
        maxcc=0.2,
        image_format=MimeType.PNG,
        config=config
    )
    print('Dates:', req.get_dates())
    data = req.get_data()
    print('Data len:', len(data))
except Exception as e:
    import traceback
    traceback.print_exc()
