"""Manual Sentinel Hub WMS evalscript probe.

This is not part of the pytest suite. It is kept as a safe manual entrypoint
for checking local Sentinel Hub credentials without hardcoded secrets.
"""

from __future__ import annotations

import os


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


def main() -> int:
    try:
        from sentinelhub import (
            BBox,
            CRS,
            CustomUrlParam,
            DataCollection,
            MimeType,
            SHConfig,
            WmsRequest,
        )
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
        time=("2023-01-01", "2023-02-01"),
        width=512,
        height=512,
        maxcc=0.5,
        image_format=MimeType.TIFF,
        custom_url_params={CustomUrlParam.EVALSCRIPT: EVALSCRIPT},
        config=config,
    )
    print("Testing WmsRequest with evalscript.")
    data = req.get_data()
    print("Num frames:", len(data))
    if data:
        print("Frame shape:", data[0].shape)
        print("Dtype:", data[0].dtype)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
