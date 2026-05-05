"""Manual Sentinel Hub WMS probe for local credential checks.

This is a development-only entrypoint. It reads credentials from environment
variables and does not run during normal verification.
"""

from __future__ import annotations

import argparse
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evalscript", action="store_true", help="Request a TIFF response with the spectral evalscript.")
    parser.add_argument(
        "--bbox",
        default="12.446,41.874,12.541,41.917",
        help="WGS84 bbox as west,south,east,north.",
    )
    parser.add_argument("--start", default="2023-01-01", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default="2023-02-01", help="End date, YYYY-MM-DD.")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--maxcc", type=float, default=0.5)
    return parser.parse_args()


def _parse_bbox(raw: str) -> list[float]:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must contain four comma-separated values")
    bbox = [float(part) for part in parts]
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError("bbox must be ordered west,south,east,north")
    return bbox


def main() -> int:
    args = _parse_args()
    try:
        from sentinelhub import BBox, CRS, CustomUrlParam, DataCollection, MimeType, SHConfig, WmsRequest
    except ImportError as exc:
        print(f"sentinelhub is not installed in this environment: {exc}")
        return 2

    instance_id = os.getenv("SENTINEL_INSTANCE_ID", "").strip()
    if not instance_id:
        print("Set SENTINEL_INSTANCE_ID before running this manual probe.")
        return 2

    try:
        bbox = _parse_bbox(args.bbox)
    except ValueError as exc:
        print(f"Invalid --bbox: {exc}")
        return 2

    config = SHConfig()
    config.instance_id = instance_id
    config.sh_client_id = os.getenv("SENTINEL_CLIENT_ID", "").strip()
    config.sh_client_secret = os.getenv("SENTINEL_CLIENT_SECRET", "").strip()

    request_kwargs = {
        "data_collection": DataCollection.SENTINEL2_L1C,
        "layer": os.getenv("SENTINEL_WMS_LAYER", "1_TRUE-COLOR-L1C"),
        "bbox": BBox(bbox, crs=CRS.WGS84),
        "time": (args.start, args.end),
        "width": args.width,
        "height": args.height,
        "maxcc": args.maxcc,
        "image_format": MimeType.TIFF if args.evalscript else MimeType.PNG,
        "config": config,
    }
    if args.evalscript:
        request_kwargs["custom_url_params"] = {CustomUrlParam.EVALSCRIPT: EVALSCRIPT}

    req = WmsRequest(**request_kwargs)
    print("Dates:", req.get_dates())
    data = req.get_data()
    print("Num frames:", len(data))
    if data:
        print("Frame shape:", getattr(data[0], "shape", "unknown"))
        print("Dtype:", getattr(data[0], "dtype", "unknown"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
