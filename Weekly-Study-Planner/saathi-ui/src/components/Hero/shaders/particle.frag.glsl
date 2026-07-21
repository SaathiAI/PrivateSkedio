precision highp float;

varying float vAlpha;
varying float vBrightness;
varying float vTrail;

void main() {
  vec2 centered = abs(gl_PointCoord - 0.5) * 2.0;
  float squareDistance = max(centered.x, centered.y);
  float edge = 1.0 - smoothstep(0.76, 1.0, squareDistance);
  float core = 1.0 - smoothstep(0.0, 0.72, squareDistance);
  vec3 ice = vec3(0.58, 0.84, 1.0);
  vec3 whiteBlue = vec3(0.9, 0.97, 1.0);
  vec3 color = mix(ice, whiteBlue, vBrightness);
  color *= 0.82 + core * 0.55 + vTrail * 0.12;
  gl_FragColor = vec4(color, edge * vAlpha);
}
