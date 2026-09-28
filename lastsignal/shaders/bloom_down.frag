#version 330 core
// 13-tap "dual box" downsample (Jimenez 2014). The first level applies a soft
// threshold and a Karis average so single hot pixels do not flicker.
in vec2 vUV;
out vec4 fragColor;
uniform sampler2D uSrc;
uniform vec2 uSrcTexel;
uniform int uFirst;
uniform float uThreshold;
uniform float uKnee;

vec3 prefilter(vec3 c) {
    float br = max(c.r, max(c.g, c.b));
    float rq = clamp(br - uThreshold + uKnee, 0.0, 2.0 * uKnee);
    rq = rq * rq / (4.0 * uKnee + 1e-5);
    float w = max(rq, br - uThreshold) / max(br, 1e-5);
    return c * w;
}
float karis(vec3 c) { return 1.0 / (1.0 + dot(c, vec3(0.2126, 0.7152, 0.0722))); }

void main() {
    vec2 t = uSrcTexel;
    vec3 a = texture(uSrc, vUV + t * vec2(-2, 2)).rgb;
    vec3 b = texture(uSrc, vUV + t * vec2(0, 2)).rgb;
    vec3 c = texture(uSrc, vUV + t * vec2(2, 2)).rgb;
    vec3 d = texture(uSrc, vUV + t * vec2(-2, 0)).rgb;
    vec3 e = texture(uSrc, vUV).rgb;
    vec3 f = texture(uSrc, vUV + t * vec2(2, 0)).rgb;
    vec3 g = texture(uSrc, vUV + t * vec2(-2, -2)).rgb;
    vec3 h = texture(uSrc, vUV + t * vec2(0, -2)).rgb;
    vec3 i = texture(uSrc, vUV + t * vec2(2, -2)).rgb;
    vec3 j = texture(uSrc, vUV + t * vec2(-1, 1)).rgb;
    vec3 k = texture(uSrc, vUV + t * vec2(1, 1)).rgb;
    vec3 l = texture(uSrc, vUV + t * vec2(-1, -1)).rgb;
    vec3 m = texture(uSrc, vUV + t * vec2(1, -1)).rgb;
    vec3 res;
    if (uFirst == 1) {
        vec3 g0 = (a + b + d + e) * 0.25, g1 = (b + c + e + f) * 0.25;
        vec3 g2 = (d + e + g + h) * 0.25, g3 = (e + f + h + i) * 0.25;
        vec3 g4 = (j + k + l + m) * 0.25;
        g0 = prefilter(g0); g1 = prefilter(g1); g2 = prefilter(g2); g3 = prefilter(g3); g4 = prefilter(g4);
        float w0 = karis(g0), w1 = karis(g1), w2 = karis(g2), w3 = karis(g3), w4 = karis(g4);
        res = (g0 * w0 * 0.125 + g1 * w1 * 0.125 + g2 * w2 * 0.125 + g3 * w3 * 0.125 + g4 * w4 * 0.5)
            / (w0 * 0.125 + w1 * 0.125 + w2 * 0.125 + w3 * 0.125 + w4 * 0.5);
    } else {
        res = e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125;
    }
    fragColor = vec4(res, 1.0);
}
