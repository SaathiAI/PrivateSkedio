precision highp float;

uniform float uTime;
uniform float uProgress;
uniform float uPixelRatio;
uniform float uPointSize;
uniform float uReducedMotion;
uniform vec2 uMouse;

attribute vec3 aFinal;
attribute vec3 aSeed;
attribute vec3 aBurst;
attribute vec3 aDirection;
attribute float aPhase;
attribute float aScale;
attribute float aBrightness;
attribute float aGroup;
attribute float aTrail;

varying float vAlpha;
varying float vBrightness;
varying float vTrail;

float saturate(float value) { return clamp(value, 0.0, 1.0); }
float smoother(float edge0, float edge1, float value) {
  float t = saturate((value - edge0) / (edge1 - edge0));
  return t * t * t * (t * (t * 6.0 - 15.0) + 10.0);
}
float easeOutExpo(float value) {
  return value >= 1.0 ? 1.0 : 1.0 - pow(2.0, -10.0 * value);
}

void main() {
  vec3 finalPosition = aFinal;
  float shimmer = sin(uTime * 2.1 + aPhase) * 0.018;
  finalPosition.y += shimmer * (0.35 + aBrightness);
  finalPosition.z += sin(uTime * 1.35 + aPhase * 1.7) * 0.025;

  vec3 driftPosition = aFinal + aDirection * (0.35 + aTrail * 0.8);
  driftPosition *= 1.0 + aTrail * 0.12;
  vec3 position = finalPosition;
  float alpha = 1.0;

  if (uReducedMotion < 0.5) {
    if (uProgress < 0.257143) {
      position = finalPosition;
    } else if (uProgress < 0.385714) {
      float t = smoother(0.257143, 0.385714, uProgress);
      float directionChoice = step(0.5, fract(aPhase * 0.159));
      vec3 controlledDrift = mix(aFinal - aDirection * 0.24, driftPosition, directionChoice);
      position = mix(finalPosition, controlledDrift, t);
      alpha = (1.0 - t) * (0.45 + 0.55 * step(t, fract(aBrightness * 7.31)));
    } else if (uProgress < 0.45) {
      position = aBurst * 1.15;
      alpha = 0.018 + 0.03 * sin(aPhase + uTime);
    } else if (uProgress < 0.521429) {
      float delayed = saturate((smoother(0.45, 0.521429, uProgress) - aGroup * 0.18) / 0.82);
      position = mix(aBurst * 1.15, aSeed, smoother(0.0, 1.0, delayed));
      alpha = smoother(0.0, 0.45, delayed);
    } else if (uProgress < 0.621429) {
      float t = easeOutExpo(saturate((uProgress - 0.521429) / 0.1));
      position = mix(aSeed, aBurst, t);
      position += aDirection * sin(t * 3.14159265) * aTrail * 0.32;
      alpha = 0.75 + 0.25 * sin(aPhase + t * 8.0);
    } else if (uProgress < 0.792857) {
      float delayed = saturate(((uProgress - 0.621429) / 0.171428 - aGroup * 0.22) / 0.78);
      float t = smoother(0.0, 1.0, delayed);
      vec3 curvedPath = mix(aBurst, finalPosition, t);
      curvedPath.y += sin(t * 3.14159265) * (aGroup - 0.5) * 0.72;
      curvedPath.z += sin(t * 3.14159265) * aDirection.z * 0.65;
      position = curvedPath;
      alpha = smoother(0.0, 0.38, delayed);
    } else {
      position = finalPosition;
    }
  }

  position.xy += uMouse * vec2(0.045, 0.025) * (0.2 + aGroup);
  vec4 modelPosition = modelMatrix * vec4(position, 1.0);
  vec4 viewPosition = viewMatrix * modelPosition;
  gl_Position = projectionMatrix * viewPosition;

  float depthScale = clamp(7.5 / -viewPosition.z, 0.55, 1.75);
  gl_PointSize = max(1.0, uPointSize * aScale * uPixelRatio * depthScale);
  vAlpha = alpha * (0.52 + aBrightness * 0.48);
  vBrightness = aBrightness;
  vTrail = aTrail;
}
