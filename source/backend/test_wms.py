"""Manual Sentinel Hub WMS connectivity probe.

This is not part of the pytest suite. It is kept as a safe manual entrypoint
for checking local Sentinel Hub credentials without hardcoded secrets.
"""

from __future__ import annotations

import os


def main() -> int:
    try:
        from sentinelhub import BBox, CRS, DataCollection, MimeType, SHConfig, WmsRequest
    except ImportError as exc:
        print(f"sentinelhub is not installed in this environment: {exc}")
        return 2

    instance_id = os.getenv("SENTINEL_INSTANCE_ID", "").strip()
    if not instance_id:
        print("Set SENTINEL_INSTANCE_ID before running this manual probe.")
        return 2

    config = SHConfig()
    config.instance_id = instance_id
    config.sh_client_id = os.getenv("SENTINEL_CLIENT_ID", "").strip()
    config.sh_client_secret = os.getenv("SENTINEL_CLIENT_SECRET", "").strip()

    req = WmsRequest(
        data_collection=DataCollection.SENTINEL2_L1C,
        layer=os.getenv("SENTINEL_WMS_LAYER", "1_TRUE-COLOR-L1C"),
        bbox=BBox([12.446, 41.874, 12.541, 41.917], crs=CRS.WGS84),
        time=("2023-01-01", "2023-02-28"),
        width=512,
        height=512,
        maxcc=0.2,
        image_format=MimeType.PNG,
        config=config,
    )
    print("Dates:", req.get_dates())
    data = req.get_data()
    print("Data len:", len(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
