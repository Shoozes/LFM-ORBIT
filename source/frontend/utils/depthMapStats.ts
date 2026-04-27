export type DepthMapStats = {
  width: number;
  height: number;
  sampleWidth: number;
  sampleHeight: number;
  sampleCount: number;
  min: number;
  max: number;
  mean: number;
  variance: number;
  stddev: number;
  backend: "webgl" | "cpu";
};

export type DepthMapStatsOptions = {
  sampleSize?: number;
  forceCpu?: boolean;
};

const VERTEX_SHADER = `
attribute vec2 a_position;
varying vec2 v_texCoord;

void main() {
  v_texCoord = (a_position + 1.0) * 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform sampler2D u_texture;
varying vec2 v_texCoord;

void main() {
  vec4 color = texture2D(u_texture, v_texCoord);
  float depth = dot(color.rgb, vec3(0.299, 0.587, 0.114));
  gl_FragColor = vec4(depth, depth * depth, 0.0, 1.0);
}
`;

function getSourceSize(source: CanvasImageSource): { width: number; height: number } {
  if (typeof HTMLVideoElement !== "undefined" && source instanceof HTMLVideoElement) {
    return { width: source.videoWidth, height: source.videoHeight };
  }
  if (typeof HTMLImageElement !== "undefined" && source instanceof HTMLImageElement) {
    return { width: source.naturalWidth || source.width, height: source.naturalHeight || source.height };
  }
  if ("width" in source && "height" in source) {
    return { width: Number(source.width), height: Number(source.height) };
  }
  return { width: 0, height: 0 };
}

function sampleShape(width: number, height: number, sampleSize = 128): { sampleWidth: number; sampleHeight: number } {
  const maxEdge = Math.max(1, Math.min(512, Math.floor(sampleSize)));
  if (width <= 0 || height <= 0) {
    return { sampleWidth: maxEdge, sampleHeight: maxEdge };
  }
  if (width >= height) {
    return { sampleWidth: maxEdge, sampleHeight: Math.max(1, Math.round((height / width) * maxEdge)) };
  }
  return { sampleWidth: Math.max(1, Math.round((width / height) * maxEdge)), sampleHeight: maxEdge };
}

function canUploadTexture(source: CanvasImageSource): source is CanvasImageSource & TexImageSource {
  return !(typeof SVGImageElement !== "undefined" && source instanceof SVGImageElement);
}

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) {
    throw new Error("Unable to create WebGL shader.");
  }
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader) || "unknown shader compile error";
    gl.deleteShader(shader);
    throw new Error(log);
  }
  return shader;
}

function createProgram(gl: WebGLRenderingContext): WebGLProgram {
  const vertex = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!program) {
    throw new Error("Unable to create WebGL program.");
  }
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program) || "unknown program link error";
    gl.deleteProgram(program);
    throw new Error(log);
  }
  return program;
}

function summarize(
  width: number,
  height: number,
  sampleWidth: number,
  sampleHeight: number,
  backend: DepthMapStats["backend"],
  visitor: (index: number) => { depth: number; square: number },
): DepthMapStats {
  const sampleCount = sampleWidth * sampleHeight;
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let sum = 0;
  let sumSquares = 0;

  for (let index = 0; index < sampleCount; index++) {
    const { depth, square } = visitor(index);
    min = Math.min(min, depth);
    max = Math.max(max, depth);
    sum += depth;
    sumSquares += square;
  }

  const mean = sampleCount > 0 ? sum / sampleCount : 0;
  const squareMean = sampleCount > 0 ? sumSquares / sampleCount : 0;
  const variance = Math.max(0, squareMean - mean * mean);

  return {
    width,
    height,
    sampleWidth,
    sampleHeight,
    sampleCount,
    min: Number.isFinite(min) ? min : 0,
    max: Number.isFinite(max) ? max : 0,
    mean,
    variance,
    stddev: Math.sqrt(variance),
    backend,
  };
}

function readWithWebGl(source: CanvasImageSource, width: number, height: number, sampleSize: number): DepthMapStats {
  if (!canUploadTexture(source)) {
    throw new Error("SVG sources are not supported by the WebGL depth-map path.");
  }
  const { sampleWidth, sampleHeight } = sampleShape(width, height, sampleSize);
  const canvas = document.createElement("canvas");
  canvas.width = sampleWidth;
  canvas.height = sampleHeight;
  const gl = canvas.getContext("webgl", {
    alpha: false,
    antialias: false,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true,
  }) as WebGLRenderingContext | null;
  if (!gl) {
    throw new Error("WebGL is unavailable.");
  }

  const program = createProgram(gl);
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
    gl.STATIC_DRAW,
  );

  const positionLocation = gl.getAttribLocation(program, "a_position");
  gl.enableVertexAttribArray(positionLocation);
  gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

  const texture = gl.createTexture();
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);

  gl.uniform1i(gl.getUniformLocation(program, "u_texture"), 0);
  gl.viewport(0, 0, sampleWidth, sampleHeight);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

  const pixels = new Uint8Array(sampleWidth * sampleHeight * 4);
  gl.readPixels(0, 0, sampleWidth, sampleHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  gl.deleteTexture(texture);
  gl.deleteBuffer(buffer);
  gl.deleteProgram(program);

  return summarize(width, height, sampleWidth, sampleHeight, "webgl", (index) => {
    const offset = index * 4;
    return {
      depth: pixels[offset] / 255,
      square: pixels[offset + 1] / 255,
    };
  });
}

function readWithCpu(source: CanvasImageSource, width: number, height: number, sampleSize: number): DepthMapStats {
  const { sampleWidth, sampleHeight } = sampleShape(width, height, sampleSize);
  const canvas = document.createElement("canvas");
  canvas.width = sampleWidth;
  canvas.height = sampleHeight;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) {
    throw new Error("2D canvas is unavailable.");
  }
  ctx.drawImage(source, 0, 0, sampleWidth, sampleHeight);
  const pixels = ctx.getImageData(0, 0, sampleWidth, sampleHeight).data;

  return summarize(width, height, sampleWidth, sampleHeight, "cpu", (index) => {
    const offset = index * 4;
    const depth = (pixels[offset] * 0.299 + pixels[offset + 1] * 0.587 + pixels[offset + 2] * 0.114) / 255;
    return { depth, square: depth * depth };
  });
}

export function readDepthMapStats(source: CanvasImageSource, options: DepthMapStatsOptions = {}): DepthMapStats {
  const { width, height } = getSourceSize(source);
  const sampleSize = options.sampleSize ?? 128;
  if (typeof document === "undefined") {
    throw new Error("Depth map stats require a browser document.");
  }
  if (!options.forceCpu) {
    try {
      return readWithWebGl(source, width, height, sampleSize);
    } catch {
      return readWithCpu(source, width, height, sampleSize);
    }
  }
  return readWithCpu(source, width, height, sampleSize);
}

export async function loadDepthMapImage(src: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.decoding = "async";
  image.src = src;
  await image.decode();
  return image;
}
