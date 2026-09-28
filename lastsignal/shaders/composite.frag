#version 330 core
// Final image: lens effects, bloom, filmic tone mapping, grade, typography,
// grain and 2.39:1 letterbox. Output is display-referred sRGB / Rec.709.
in vec2 vUV;
out vec4 fragColor;

uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform sampler2D uStreak;
uniform sampler2D uText;      // full-frame text coverage (r), mipmapped
uniform vec2  uOutRes;
uniform float uActiveH;       // active picture height in output pixels
uniform float uExposure;
uniform float uBloomGain;
uniform float uStreakGain;
uniform vec3  uStreakTint;
uniform float uCA;            // chromatic aberration
uniform float uVignette;
uniform float uGrain;
uniform float uFade;          // 0 = black, 1 = full image
uniform float uFlash;         // white flash (pre tonemap, additive)
uniform float uGlitch;        // signal interference
uniform float uShake;         // unused by shader, kept for completeness
uniform float uFrame;
uniform float uSaturation;
uniform float uContrast;
uniform vec3  uLift;
uniform vec3  uGain;
uniform float uTextOpacity;
uniform vec3  uTextColor;
uniform float uTextGlow;
uniform float uTextSweep;     // x position (0..1) of the light sweep, <0 disabled
uniform float uTextFlicker;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 acesFit(vec3 color) {
    const mat3 inM = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
    const mat3 outM = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
    color = inM * color;
    vec3 a = color * (color + 0.0245786) - 0.000090537;
    vec3 b = color * (0.983729 * color + 0.4329510) + 0.238081;
    color = a / b;
    return clamp(outM * color, 0.0, 1.0);
}

vec3 toSRGB(vec3 c) {
    c = clamp(c, 0.0, 1.0);
    return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
}

vec3 sampleScene(vec2 uv) {
    vec2 dc = uv - 0.5;
    float k = uCA * dot(dc, dc);
    vec3 c;
    c.r = texture(uScene, uv - dc * k).r;
    c.g = texture(uScene, uv).g;
    c.b = texture(uScene, uv + dc * k).b;
    return c;
}

void main() {
    vec2 px = gl_FragCoord.xy;
    float barH = 0.5 * (uOutRes.y - uActiveH);
    if (px.y < barH || px.y > uOutRes.y - barH) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    vec2 uv = vec2(px.x / uOutRes.x, (px.y - barH) / uActiveH);

    // signal interference: tearing bands + channel split
    float split = 0.0;
    if (uGlitch > 0.0) {
        float band = floor(uv.y * 38.0);
        float n = hash12(vec2(band, floor(uFrame)));
        float on = step(1.0 - 0.35 * uGlitch, n);
        uv.x += on * (hash12(vec2(band, uFrame + 7.0)) - 0.5) * 0.08 * uGlitch;
        split = uGlitch * (0.004 + 0.01 * on);
    }

    vec3 hdr;
    if (split > 0.0) {
        hdr = vec3(texture(uScene, uv + vec2(split, 0)).r, texture(uScene, uv).g, texture(uScene, uv - vec2(split, 0)).b);
    } else {
        hdr = sampleScene(uv);
    }
    vec3 bloom = texture(uBloom, uv).rgb;
    vec3 streak = texture(uStreak, uv).rgb;
    hdr += bloom * uBloomGain;
    hdr += streak * uStreakTint * uStreakGain;
    hdr += vec3(uFlash);

    // vignette (before tone mapping so highlights roll off naturally)
    vec2 vc = (uv - 0.5) * vec2(uOutRes.x / uActiveH, 1.0);
    float vig = 1.0 - uVignette * smoothstep(0.35, 1.25, length(vc));
    hdr *= vig;

    vec3 c = acesFit(hdr * uExposure);

    // grade: lift / gain, contrast about mid grey, saturation
    c = c * uGain + uLift * (1.0 - c);
    c = max(c, 0.0);
    vec3 lg = log2(c + 1e-4);
    lg = (lg - log2(0.18)) * uContrast + log2(0.18);
    c = exp2(lg) - 1e-4;
    float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = mix(vec3(luma), c, uSaturation);
    c = clamp(c, 0.0, 1.0);

    // typography (display referred, composited over the graded image)
    vec2 tuv = px / uOutRes;
    float ta = texture(uText, tuv).r;
    if (uTextOpacity > 0.0) {
        float g1 = textureLod(uText, tuv, 2.5).r;
        float g2 = textureLod(uText, tuv, 4.5).r;
        float sweep = 0.0;
        if (uTextSweep > -0.5) {
            float dx = tuv.x - uTextSweep + (tuv.y - 0.5) * 0.25;
            sweep = exp(-dx * dx / 0.0025);
        }
        float flick = 1.0 - uTextFlicker * step(0.5, hash12(vec2(floor(uFrame), 3.0)));
        float a = ta * uTextOpacity * flick;
        vec3 tc = uTextColor * (1.0 + sweep * 0.9);
        c = mix(c, tc, a);
        c += uTextColor * (g1 * 0.35 + g2 * 0.25) * uTextGlow * uTextOpacity * flick * (1.0 + sweep * 2.0);
        c += vec3(1.0, 0.85, 0.65) * sweep * ta * uTextOpacity * 0.35;
    }

    // fade to black is applied in linear light
    c = c * uFade;

    vec3 outc = toSRGB(c);
    // film grain (luma weighted) + dither against banding
    float r1 = hash12(px + fract(uFrame * 0.6180339) * 1000.0);
    float r2 = hash12(px * 1.37 + fract(uFrame * 0.3819660) * 1000.0 + 17.0);
    float grain = (r1 + r2 - 1.0);
    float gl = dot(outc, vec3(0.333));
    // grain lives in the picture, not in true black (cuts to black stay black)
    float gw = (0.35 + 0.65 * (1.0 - abs(gl * 2.0 - 1.0))) * smoothstep(0.0, 0.04, gl + uFade * 0.02);
    outc += grain * uGrain * gw * min(uFade * 4.0, 1.0);
    outc += (r1 - 0.5) / 255.0 * step(0.001, uFade);
    fragColor = vec4(clamp(outc, 0.0, 1.0), 1.0);
}
