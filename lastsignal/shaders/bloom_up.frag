#version 330 core
// 9-tap tent upsample of the coarser level, added onto this level.
in vec2 vUV;
out vec4 fragColor;
uniform sampler2D uLow;   // coarser level (already accumulated)
uniform sampler2D uCur;   // this level's downsample
uniform vec2 uLowTexel;
uniform float uRadius;
uniform float uMix;
void main() {
    vec2 t = uLowTexel * uRadius;
    vec3 s = texture(uLow, vUV).rgb * 4.0;
    s += (texture(uLow, vUV + vec2(t.x, 0)).rgb + texture(uLow, vUV - vec2(t.x, 0)).rgb +
          texture(uLow, vUV + vec2(0, t.y)).rgb + texture(uLow, vUV - vec2(0, t.y)).rgb) * 2.0;
    s += texture(uLow, vUV + t).rgb + texture(uLow, vUV - t).rgb +
         texture(uLow, vUV + vec2(t.x, -t.y)).rgb + texture(uLow, vUV + vec2(-t.x, t.y)).rgb;
    s /= 16.0;
    fragColor = vec4(texture(uCur, vUV).rgb + s * uMix, 1.0);
}
