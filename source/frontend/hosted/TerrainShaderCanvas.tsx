import { useEffect, useRef } from "react";

type TerrainShaderCanvasProps = {
  onStatus?: (status: string) => void;
};

const VERTEX_SHADER = `#version 300 es
in vec2 aPosition;
void main() { gl_Position = vec4(aPosition, 0.0, 1.0); }`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
out vec4 outColor;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
    f.y
  );
}

float fbm(vec2 p) {
  float value = 0.0;
  float amplitude = 0.5;
  for (int i = 0; i < 6; i++) {
    value += amplitude * noise(p);
    p = p * 2.03 + vec2(17.0, 9.0);
    amplitude *= 0.5;
  }
  return value;
}

void main() {
  vec2 uv = (2.0 * gl_FragCoord.xy - uResolution.xy) / uResolution.y;
  vec2 p = uv * 1.2 + vec2(0.0, 1.7);
  p.y += uTime * 0.025;
  float terrain = fbm(p * 1.15) - 0.47;
  float water = 1.0 - smoothstep(-0.015, 0.04, terrain);
  float ridges = fbm(p * 3.8 + vec2(2.0, -1.0));
  float landLight = smoothstep(-0.08, 0.6, terrain) * (0.58 + 0.42 * ridges);

  vec3 land = mix(vec3(0.035, 0.10, 0.12), vec3(0.40, 0.62, 0.42), landLight);
  vec2 waterP = p * 3.0 + vec2(uTime * 0.08, -uTime * 0.035);
  float waves = fbm(waterP) * 0.22 + 0.78;
  vec3 ocean = mix(vec3(0.008, 0.035, 0.10), vec3(0.02, 0.25, 0.34), waves);
  float coastline = 1.0 - smoothstep(0.0, 0.045, abs(terrain));
  vec3 color = mix(land, ocean, water);
  color += vec3(0.30, 0.72, 0.78) * coastline * 0.34;
  color *= 0.86 + 0.14 * sin(uv.x * 2.1 + uTime * 0.2);
  outColor = vec4(pow(max(color, 0.0), vec3(0.86)), 1.0);
}`;

function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  source: string,
): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL shader allocation failed");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader) || "WebGL shader compilation failed";
    gl.deleteShader(shader);
    throw new Error(info);
  }
  return shader;
}

function createProgram(gl: WebGL2RenderingContext): WebGLProgram {
  const vertex = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!program) throw new Error("WebGL program allocation failed");
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program) || "WebGL program link failed";
    gl.deleteProgram(program);
    throw new Error(info);
  }
  return program;
}

export default function TerrainShaderCanvas({ onStatus }: TerrainShaderCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: true,
      depth: false,
      preserveDrawingBuffer: false,
    });
    if (!gl) {
      onStatus?.("WebGL 2 is unavailable; the static presentation remains usable.");
      return undefined;
    }

    let program: WebGLProgram;
    try {
      program = createProgram(gl);
    } catch (error) {
      onStatus?.(error instanceof Error ? error.message : "WebGL setup failed");
      return undefined;
    }

    const buffer = gl.createBuffer();
    if (!buffer) {
      onStatus?.("WebGL buffer allocation failed");
      gl.deleteProgram(program);
      return undefined;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    gl.useProgram(program);
    const position = gl.getAttribLocation(program, "aPosition");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const resolution = gl.getUniformLocation(program, "uResolution");
    const time = gl.getUniformLocation(program, "uTime");
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reducedMotion = motionQuery.matches;
    let isVisible = document.visibilityState === "visible";
    let isIntersecting = true;
    const start = performance.now();
    let frame = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      const width = Math.max(1, Math.floor(canvas.clientWidth * dpr));
      const height = Math.max(1, Math.floor(canvas.clientHeight * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
    };
    const draw = (now: number) => {
      resize();
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform1f(time, reducedMotion ? 0 : (now - start) * 0.001);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    };
    const stop = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
    };
    const schedule = () => {
      if (frame || reducedMotion || !isVisible || !isIntersecting) return;
      frame = requestAnimationFrame((now) => {
        frame = 0;
        draw(now);
        schedule();
      });
    };
    const updateMotion = (event: MediaQueryListEvent) => {
      reducedMotion = event.matches;
      draw(performance.now());
      if (reducedMotion) stop();
      else schedule();
    };
    const updateVisibility = () => {
      isVisible = document.visibilityState === "visible";
      if (isVisible) {
        draw(performance.now());
        schedule();
      } else {
        stop();
      }
    };
    const observer = typeof IntersectionObserver === "undefined"
      ? null
      : new IntersectionObserver(([entry]) => {
          isIntersecting = entry?.isIntersecting ?? true;
          if (isIntersecting) {
            draw(performance.now());
            schedule();
          } else {
            stop();
          }
        }, { threshold: 0.01 });

    window.addEventListener("resize", resize, { passive: true });
    document.addEventListener("visibilitychange", updateVisibility);
    motionQuery.addEventListener?.("change", updateMotion);
    observer?.observe(canvas);
    resize();
    draw(performance.now());
    schedule();
    onStatus?.("WebGL terrain online");
    return () => {
      stop();
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", updateVisibility);
      motionQuery.removeEventListener?.("change", updateMotion);
      observer?.disconnect();
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, [onStatus]);

  return <canvas ref={canvasRef} className="hosted-terrain-canvas" aria-hidden="true" />;
}
