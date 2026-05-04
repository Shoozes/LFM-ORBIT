//VERSION=3

function setup() {
  return {
    input: [{
      bands: [
        "B02",
        "B03",
        "B04",
        "B05",
        "B07",
        "B08",
        "B8A",
        "B11",
        "B12",
        "SCL",
        "dataMask"
      ],
      units: "REFLECTANCE"
    }],
    output: [
      { id: "features", bands: 8, sampleType: "FLOAT32" },
      { id: "visual", bands: 3, sampleType: "UINT8" }
    ]
  };
}

function clamp01(value) {
  return Math.max(0.0, Math.min(1.0, value));
}

function safeIndex(a, b) {
  var denominator = a + b;
  if (Math.abs(denominator) < 0.000001) return 0.0;
  return (a - b) / denominator;
}

function isInvalid(sample) {
  var scl = Math.round(sample.SCL);
  if (sample.dataMask === 0) return true;

  // SCL: 3 cloud shadow, 8 medium cloud, 9 high cloud, 10 cirrus, 11 snow/ice.
  return scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11;
}

function evaluatePixel(sample) {
  var ndwi = safeIndex(sample.B03, sample.B08);
  var mndwi = safeIndex(sample.B03, sample.B11);
  var ndvi = safeIndex(sample.B08, sample.B04);
  var ndci = safeIndex(sample.B05, sample.B04);

  // Floating algae style signal using red/red-edge/NIR interpolation.
  var fai = sample.B07 - (
    sample.B04 + (sample.B8A - sample.B04) * ((783.0 - 665.0) / (865.0 - 665.0))
  );

  var water = ndwi > 0.0 || mndwi > 0.0 || Math.round(sample.SCL) === 6;
  var valid = !isInvalid(sample) && water ? 1.0 : 0.0;
  var bloomScore = valid > 0.0 ? clamp01((ndci * 2.5) + (fai * 10.0)) : 0.0;

  return {
    features: [
      ndci,
      fai,
      ndwi,
      mndwi,
      ndvi,
      safeIndex(sample.B03, sample.B11),
      bloomScore,
      valid
    ],
    visual: [
      Math.round(clamp01(sample.B04 * 4.0) * 255),
      Math.round(clamp01(sample.B03 * 4.0) * 255),
      Math.round(clamp01(sample.B02 * 4.0) * 255)
    ]
  };
}
