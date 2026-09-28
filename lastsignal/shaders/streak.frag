#version 330 core
// Separable wide horizontal blur used for the anamorphic lens streak.
in vec2 vUV;
out vec4 fragColor;
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform float uSpread;
uniform float uThreshold;
void main() {
    vec3 acc = vec3(0.0);
    float wsum = 0.0;
    for (int i = -12; i <= 12; i++) {
        float x = float(i);
        float w = exp(-abs(x) * 0.22);
        vec3 c = texture(uSrc, vUV + vec2(x * uSpread * uTexel.x, 0.0)).rgb;
        c = max(c - uThreshold, 0.0);
        acc += c * w;
        wsum += w;
    }
    fragColor = vec4(acc / wsum, 1.0);
}
