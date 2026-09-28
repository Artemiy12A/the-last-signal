#version 330 core
// THE LAST SIGNAL - scene shader
//
// Renders one HDR sample of the scene:
//   * a Schwarzschild black hole, ray traced by integrating null geodesics
//     (units: Schwarzschild radius rs = 1, photon sphere r = 1.5, ISCO r = 3)
//   * a thin, turbulent, relativistically beamed accretion disk with
//     multiple images (primary, secondary, photon ring)
//   * a lensed sky: NASA Milky Way diffuse map + analytic point stars whose
//     brightness follows gravitational magnification
//   * a small deep-space probe (signed distance field), lit by the disk
//
// Several jittered passes are accumulated by the host for anti-aliasing.

in vec2 vUV;
out vec4 fragColor;

uniform vec2  uRes;
uniform vec2  uJitter;
uniform vec3  uCamPos;
uniform mat3  uCamRot;        // columns: right, up, forward
uniform float uTanHalfFovY;
uniform float uPixelAngle;    // nominal angular size of one pixel (rad)
uniform float uTime;          // global time, seconds
uniform float uPass;
uniform float uWeight;        // 1 / number of accumulated passes

// black hole
uniform float uBH;            // 0 = flat space, 1 = black hole present
uniform float uStepK;
uniform int   uMaxSteps;
uniform float uEscapeR;

// accretion disk
uniform float uDiskGain;
uniform float uDiskIgnite;    // ignition front radius; >= uDiskOut means fully lit
uniform float uDiskTime;
uniform float uDiskTemp;      // peak temperature, Kelvin
uniform float uDoppler;       // 0..1 artistic doppler strength
uniform float uDiskIn;
uniform float uDiskOut;
uniform float uGlow;          // volumetric haze strength
uniform float uRingBoost;     // extra gain for higher order images

// sky
uniform sampler2D uSky;
uniform float uSkyScale;      // decode scale for the sky texture
uniform mat3  uSkyRot;
uniform float uSkyGain;
uniform float uStarGain;
uniform sampler2D uBB;        // blackbody chromaticity LUT (log T)

// probe
uniform float uShip;
uniform vec3  uShipPos;
uniform mat3  uShipRot;       // columns: ship right, up, forward in world space
uniform float uShipScale;
uniform vec3  uKeyDir;        // direction TO the key light (world)
uniform vec3  uKeyCol;
uniform vec3  uFillCol;
uniform vec3  uRimCol;
uniform float uBeacon;        // beacon intensity (blinks with the signal)
uniform float uEngine;        // ion engine glow

const float PI = 3.14159265359;
const float TAU = 6.28318530718;

// ---------------------------------------------------------------- hashing
uvec3 pcg3d(uvec3 v) {
    v = v * 1664525u + 1013904223u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    v ^= v >> 16u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    return v;
}
vec3 hash33(vec3 p) {
    return vec3(pcg3d(uvec3(ivec3(floor(p))))) * (1.0 / 4294967295.0);
}
float hash13(vec3 p) { return hash33(p).x; }

float vnoise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    float a = hash13(i);
    float b = hash13(i + vec3(1, 0, 0));
    float c = hash13(i + vec3(0, 1, 0));
    float d = hash13(i + vec3(1, 1, 0));
    float e = hash13(i + vec3(0, 0, 1));
    float g = hash13(i + vec3(1, 0, 1));
    float h = hash13(i + vec3(0, 1, 1));
    float k = hash13(i + vec3(1, 1, 1));
    return mix(mix(mix(a, b, u.x), mix(c, d, u.x), u.y),
               mix(mix(e, g, u.x), mix(h, k, u.x), u.y), u.z);
}

float fbm(vec3 p, int oct) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 6; i++) {
        if (i >= oct) break;
        s += a * vnoise(p);
        p = p * 2.03 + vec3(1.7, 9.2, 3.1);
        a *= 0.5;
    }
    return s;
}

// ------------------------------------------------------------- blackbody
vec3 blackbody(float T) {
    float u = (log(clamp(T, 800.0, 40000.0)) - log(800.0)) / (log(40000.0) - log(800.0));
    return texture(uBB, vec2(u, 0.5)).rgb;
}

// ------------------------------------------------------------- the disk
// normalised Novikov-Thorne-like temperature profile, peak ~1
float diskTempProfile(float r) {
    float x = uDiskIn / r;
    return pow(x, 0.75) * pow(max(1.0 - sqrt(x), 0.0), 0.25) * 2.05;
}

// doppler * gravitational shift for gas orbiting at radius r, seen along ray direction rd
float diskShift(vec3 p, float r, vec3 rd) {
    float beta = sqrt(0.5 / max(r - 1.0, 0.05));
    beta = min(beta, 0.75) * uDoppler;
    vec3 vdir = normalize(vec3(-p.z, 0.0, p.x));
    float gamma = inversesqrt(1.0 - beta * beta);
    float gD = 1.0 / (gamma * (1.0 + beta * dot(vdir, rd)));
    float gG = sqrt(max(1.0 - 1.0 / r, 0.0));
    return gD * mix(1.0, gG, 0.8);
}

// structure of the disk gas: x = density (opacity), y = emission multiplier
vec2 diskDensity(float r, float phi, int oct) {
    float omega = 0.7071 * pow(r, -1.5);
    float ang = phi - omega * uDiskTime;
    vec2 cs = vec2(cos(ang), sin(ang));
    float lr = log(r);
    // broad clumps and spiral lanes
    float big = fbm(vec3(cs * 1.7, lr * 4.0 + 0.3 * ang), 3);
    // fine concentric filaments, warped by the broad field
    float fil = fbm(vec3(cs * 2.6, lr * 26.0 + big * 3.0), oct);
    // ring gaps (Saturn-like lanes that drift slowly)
    float gap = fbm(vec3(cs * 0.55, lr * 10.0 + 4.0), 2);
    float d = smoothstep(0.15, 0.85, big) * 0.6 + 0.4;
    d *= 0.3 + 1.2 * smoothstep(0.28, 0.78, fil);
    d *= 0.55 + 0.45 * smoothstep(0.30, 0.52, gap);
    // hot knots: compact bright clumps riding the flow
    float kn = fbm(vec3(cs * 6.5, lr * 16.0 + big * 2.5), oct > 3 ? 3 : 2);
    float knots = smoothstep(0.52, 0.85, kn);
    // radial envelope: sharp inner edge at ISCO, long fading outskirts
    float inner = smoothstep(uDiskIn, uDiskIn * 1.12, r);
    float outer = 1.0 - smoothstep(uDiskOut * 0.45, uDiskOut, r);
    float env = inner * outer * outer;
    return vec2(d * env, 1.0 + 1.8 * knots * knots);
}

// emission (rgb) and opacity (a) where a ray pierces the disk plane
vec4 diskSample(vec3 p, vec3 rd, int order) {
    float r = length(p.xz);
    float phi = atan(p.z, p.x);
    int oct = order == 0 ? 5 : 3;
    vec2 dn = diskDensity(r, phi, oct);
    float dens = dn.x;
    float Tn = diskTempProfile(r);
    float g = diskShift(p, r, rd);
    // knots run hotter
    vec3 col = blackbody(uDiskTemp * Tn * g * (0.92 + 0.12 * (dn.y - 1.0)));
    float I = pow(Tn, 2.3) * pow(g, 3.2);
    // ignition front for the reveal: light races outward from the ISCO
    float ign = smoothstep(uDiskIgnite, uDiskIgnite - 1.6, r);
    float flash = exp(-abs(r - uDiskIgnite) * 1.8) * step(uDiskIgnite, uDiskOut + 2.0) * 1.5;
    I *= ign + flash * ign;
    float boost = order == 0 ? 1.0 : uRingBoost;
    float alpha = clamp(1.0 - exp(-dens * 2.6), 0.0, 0.97) * (0.25 + 0.75 * ign);
    return vec4(col * I * dens * dn.y * uDiskGain * 3.4 * boost, alpha);
}

// soft haze hugging the disk (cheap, no noise)
vec3 diskHaze(vec3 x, vec3 rd) {
    float r = length(x.xz);
    if (r < uDiskIn * 0.95 || r > uDiskOut * 1.2) return vec3(0.0);
    float H = 0.05 + 0.06 * r;
    float v = exp(-(x.y * x.y) / (H * H));
    float Tn = diskTempProfile(max(r, uDiskIn * 1.01));
    float g = diskShift(x, r, rd);
    float ign = smoothstep(uDiskIgnite, uDiskIgnite - 2.5, r);
    float outer = 1.0 - smoothstep(uDiskOut * 0.5, uDiskOut * 1.2, r);
    return blackbody(uDiskTemp * Tn * g) * pow(Tn, 2.0) * pow(g, 3.0) * v * ign * outer;
}

// ------------------------------------------------------------- the sky
vec3 skyDir(vec3 d) { return uSkyRot * d; }

vec2 equirect(vec3 d) {
    return vec2(atan(d.z, d.x) / TAU + 0.5, 0.5 - asin(clamp(d.y, -1.0, 1.0)) / PI);
}

// Analytic stars: one candidate per cell of a cube-sphere grid. Brightness is
// flux conserving with respect to the local lensing magnification: fp is the
// angular footprint of this pixel on the (lensed) sky.
vec3 starLayer(vec3 d, float cells, float fp, float seed, float prob, float fluxK, float mwBoost) {
    vec3 ad = abs(d);
    vec3 n; vec2 uv; float ma;
    if (ad.x >= ad.y && ad.x >= ad.z) { ma = ad.x; uv = vec2(d.z, d.y) / ma; n = vec3(sign(d.x), 0, 0); }
    else if (ad.y >= ad.z)           { ma = ad.y; uv = vec2(d.x, d.z) / ma; n = vec3(0, sign(d.y), 0); }
    else                             { ma = ad.z; uv = vec2(d.x, d.y) / ma; n = vec3(0, 0, sign(d.z)); }
    vec2 g = (uv * 0.5 + 0.5) * cells;
    vec2 id = floor(g);
    float faceId = dot(n, vec3(1.0, 2.0, 3.0)) + 3.0;
    float sigma0 = uPixelAngle * 0.55;
    float sig = max(sigma0, fp * 0.6);
    // surface brightness is conserved: magnified stars grow, demagnified ones dim
    float norm = (uPixelAngle * uPixelAngle) / (2.0 * PI * sig * sig);
    vec3 acc = vec3(0.0);
    for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
        vec2 c = id + vec2(i, j);
        vec3 h = hash33(vec3(c, faceId * 131.0 + seed));
        if (h.z > prob * mwBoost) continue;
        vec2 suv = (c + 0.15 + 0.7 * h.xy) / cells * 2.0 - 1.0;
        vec3 sd;
        if (n.x != 0.0)      sd = normalize(vec3(n.x, suv.y, suv.x));
        else if (n.y != 0.0) sd = normalize(vec3(suv.x, n.y, suv.y));
        else                 sd = normalize(vec3(suv.x, suv.y, n.z));
        vec3 dd = d - sd;
        float a2 = dot(dd, dd);
        vec3 h2 = hash33(vec3(c.yx * 1.37, faceId + seed * 7.1));
        float flux = fluxK * pow(max(h2.x, 1e-4), -1.35) * 0.02;
        flux = min(flux, fluxK * 40.0);
        float T = mix(3200.0, 11000.0, h2.y * h2.y);
        vec3 tint = mix(vec3(1.0), blackbody(T), 0.55);
        acc += tint * flux * norm * exp(-0.5 * a2 / (sig * sig));
    }
    return acc;
}

vec3 skyColor(vec3 dWorld, float fp) {
    vec3 d = skyDir(dWorld);
    vec2 uv = equirect(d);
    // gradients for trilinear filtering (handles strong lensing compression)
    vec2 dx = dFdx(uv), dy = dFdy(uv);
    dx.x -= round(dx.x); dy.x -= round(dy.x);
    vec3 enc = textureGrad(uSky, uv, dx, dy).rgb;
    vec3 mw = pow(enc, vec3(2.4)) * uSkyScale;
    float mwl = dot(mw, vec3(0.2126, 0.7152, 0.0722)) / uSkyScale;
    float boost = 1.0 + 2.5 * smoothstep(0.02, 0.4, mwl);
    vec3 stars = vec3(0.0);
    stars += starLayer(d, 42.0, fp, 1.0, 0.55, 1.0, 1.0);
    stars += starLayer(d, 140.0, fp, 2.0, 0.40, 0.30, boost);
    stars += starLayer(d, 420.0, fp, 3.0, 0.22, 0.10, boost);
    // granular star clouds: very faint, dense, only where the galaxy is bright
    float cloud = smoothstep(0.03, 0.5, mwl);
    if (cloud > 0.0) stars += starLayer(d, 1300.0, fp, 4.0, 0.9 * cloud, 0.035, 1.0) * (0.5 + cloud);
    return mw * uSkyGain + stars * uStarGain;
}

// ------------------------------------------------------------- the probe
float sdCappedCyl(vec3 p, float h, float r) {
    vec2 d = abs(vec2(length(p.xy), p.z)) - vec2(r, h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}
float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdPrism10(vec3 p, float r, float h) {
    // decagonal prism along z
    float a = atan(p.y, p.x);
    float s = TAU / 10.0;
    a = mod(a + s * 0.5, s) - s * 0.5;
    vec2 q = length(p.xy) * vec2(cos(a), abs(sin(a)));
    vec2 d = vec2(q.x - r, abs(p.z) - h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

// material ids: 1 dish, 2 gold bus, 3 dark metal, 4 rtg, 5 feed
vec2 shipMap(vec3 p) {
    // dish: spherical cap shell (focal length Rs/2), vertex at z=0.15, opening towards -z
    const float Rs = 1.3;
    vec3 dc = p - vec3(0.0, 0.0, 0.15 - Rs);
    float zRim = 0.15 - Rs + sqrt(Rs * Rs - 1.0);
    float dDish = max(abs(length(dc) - Rs) - 0.02, zRim - p.z);
    vec2 res = vec2(dDish, 1.0);
    // dish rim ring
    float rho = length(p.xy);
    float rim = length(vec2(rho - 1.0, p.z - zRim)) - 0.024;
    if (rim < res.x) res = vec2(rim, 3.0);
    float f = Rs * 0.5;
    // feed horn at focus + three struts
    vec3 fp = vec3(0.0, 0.0, 0.15 - f);
    float feed = sdCappedCyl(p - fp - vec3(0, 0, 0.03), 0.07, 0.06);
    if (feed < res.x) res = vec2(feed, 5.0);
    for (int i = 0; i < 3; i++) {
        float a = float(i) * TAU / 3.0 + 0.5;
        vec3 rp = vec3(cos(a) * 0.97, sin(a) * 0.97, zRim + 0.01);
        float st = sdCapsule(p, rp, fp, 0.009);
        if (st < res.x) res = vec2(st, 3.0);
    }
    // bus behind the dish
    float bus = sdPrism10(p - vec3(0, 0, 0.42), 0.42, 0.2);
    if (bus < res.x) res = vec2(bus, 2.0);
    // thruster module
    float thr = sdCappedCyl(p - vec3(0, 0, 0.72), 0.1, 0.16);
    if (thr < res.x) res = vec2(thr, 3.0);
    float noz = max(sdCappedCyl(p - vec3(0, 0, 0.86), 0.06, 0.13 + (p.z - 0.8) * 0.4), -(length(p.xy) - 0.09));
    if (noz < res.x) res = vec2(noz, 3.0);
    // RTG boom (down-left) with three finned generators
    vec3 ra = vec3(-0.35, -0.15, 0.45), rb = vec3(-2.1, -0.75, 0.55);
    float rtgB = sdCapsule(p, ra, rb, 0.028);
    if (rtgB < res.x) res = vec2(rtgB, 3.0);
    for (int i = 0; i < 3; i++) {
        vec3 c = mix(vec3(-1.25, -0.46, 0.5), rb, float(i) / 2.0);
        vec3 q = p - c;
        vec3 ax = normalize(rb - ra);
        float t = dot(q, ax);
        float rr = length(q - ax * t);
        float fa = atan(q.y, q.z);
        float fins = 0.085 + 0.03 * smoothstep(0.6, 0.95, abs(cos(fa * 3.0)));
        float gen = max(rr - fins, abs(t) - 0.17);
        if (gen < res.x) res = vec2(gen, 4.0);
    }
    // science boom (right) with instrument platform
    vec3 sa = vec3(0.38, 0.05, 0.45), sb = vec3(2.3, 0.3, 0.6);
    float sci = sdCapsule(p, sa, sb, 0.03);
    if (sci < res.x) res = vec2(sci, 3.0);
    float plat = sdBox(p - sb - vec3(0.12, 0.0, 0.0), vec3(0.16, 0.12, 0.14));
    if (plat < res.x) res = vec2(plat, 2.0);
    float cam = sdCappedCyl(p - sb - vec3(0.12, 0.0, -0.2), 0.08, 0.06);
    if (cam < res.x) res = vec2(cam, 3.0);
    // long magnetometer boom, up and back
    float mag = sdCapsule(p, vec3(0.1, 0.35, 0.5), vec3(0.9, 3.6, 1.3), 0.012);
    if (mag < res.x) res = vec2(mag, 3.0);
    // low-gain antenna on the dish vertex backside
    return res;
}

vec3 shipNormal(vec3 p) {
    const vec2 e = vec2(0.0015, 0.0);
    return normalize(vec3(
        shipMap(p + e.xyy).x - shipMap(p - e.xyy).x,
        shipMap(p + e.yxy).x - shipMap(p - e.yxy).x,
        shipMap(p + e.yyx).x - shipMap(p - e.yyx).x));
}

float shipShadow(vec3 p, vec3 l) {
    float res = 1.0, t = 0.06;
    for (int i = 0; i < 28; i++) {
        float h = shipMap(p + l * t).x;
        res = min(res, 6.0 * h / t);
        t += clamp(h, 0.03, 0.25);
        if (res < 0.01 || t > 6.0) break;
    }
    return clamp(res, 0.0, 1.0);
}

// returns rgb + coverage; also the emissive glow (beacon, engine) through glowOut
vec4 renderShip(vec3 roW, vec3 rdW, float pixAng, out vec3 glowOut) {
    glowOut = vec3(0.0);
    if (uShip < 0.5) return vec4(0.0);
    mat3 invR = transpose(uShipRot);
    vec3 ro = invR * (roW - uShipPos) / uShipScale;
    vec3 rd = invR * rdW;

    // emissive points in local space
    vec3 beaconP = vec3(0.0, 0.45, 0.42);
    vec3 engineP = vec3(0.0, 0.0, 0.95);

    // bounding sphere
    float bR = 4.2;
    float b = dot(ro, rd);
    float c = dot(ro, ro) - bR * bR;
    float disc = b * b - c;
    float cover = 0.0;
    vec3 col = vec3(0.0);
    float tHit = 1e9;
    if (disc > 0.0) {
        float t = max(-b - sqrt(disc), 0.0);
        float tEnd = -b + sqrt(disc);
        float bestRatio = 1e9; float bestT = t;
        for (int i = 0; i < 140; i++) {
            vec3 p = ro + rd * t;
            float d = shipMap(p).x;
            float pr = pixAng * t * 0.9;           // pixel cone radius (local units)
            float ratio = d / max(pr, 1e-5);
            if (ratio < bestRatio) { bestRatio = ratio; bestT = t; }
            if (d < pr * 0.25) { bestRatio = -1.0; bestT = t; break; }
            t += max(d * 0.8, pr * 0.3);
            if (t > tEnd) break;
        }
        // solid hit -> opaque; near miss -> partial coverage (anti-aliased edges, thin booms)
        cover = bestRatio < 0.0 ? 1.0 : smoothstep(0.0, 1.0, clamp(1.0 - bestRatio, 0.0, 1.0));
        if (cover > 0.0) {
            tHit = bestT;
            vec3 p = ro + rd * bestT;
            // converge onto the surface before shading (removes contour banding)
            for (int k = 0; k < 4; k++) p += rd * shipMap(p).x;
            vec2 m = shipMap(p);
            vec3 n = shipNormal(p);
            vec3 L = normalize(invR * uKeyDir);
            vec3 V = -rd;
            // materials
            vec3 alb; float rough; float metal;
            if (m.y < 1.5)      { alb = vec3(0.62, 0.60, 0.57); rough = 0.45; metal = 0.0; }
            else if (m.y < 2.5) { alb = vec3(1.0, 0.72, 0.32); rough = 0.28; metal = 1.0;
                                  // crinkled foil
                                  n = normalize(n + 0.35 * (vec3(vnoise(p * 40.0), vnoise(p * 40.0 + 7.0), vnoise(p * 40.0 + 13.0)) - 0.5)); }
            else if (m.y < 3.5) { alb = vec3(0.16, 0.16, 0.17); rough = 0.4; metal = 0.6; }
            else if (m.y < 4.5) { alb = vec3(0.10, 0.09, 0.09); rough = 0.6; metal = 0.2; }
            else                { alb = vec3(0.75, 0.74, 0.70); rough = 0.35; metal = 0.3; }
            float ndl = max(dot(n, L), 0.0);
            float sh = ndl > 0.0 ? shipShadow(p + n * 0.03, L) : 0.0;
            vec3 H = normalize(L + V);
            float ndh = max(dot(n, H), 0.0);
            float a2 = rough * rough * rough * rough;
            float dnm = ndh * ndh * (a2 - 1.0) + 1.0;
            float D = a2 / (PI * dnm * dnm);
            vec3 F0 = mix(vec3(0.04), alb, metal);
            vec3 F = F0 + (1.0 - F0) * pow(1.0 - max(dot(H, V), 0.0), 5.0);
            vec3 spec = D * F * 0.25;
            vec3 diff = alb * (1.0 - metal * 0.85) / PI;
            col = (diff + spec) * uKeyCol * ndl * sh * PI;
            // the beacon is a real light: it paints the hull red on every ping
            vec3 bl = beaconP + vec3(0.0, 0.06, 0.0) - p;
            float bd2 = dot(bl, bl);
            vec3 bL = bl * inversesqrt(bd2);
            float bndl = max(dot(n, bL), 0.0);
            col += (alb * (1.0 - metal * 0.6) + F0 * 0.5) * vec3(1.0, 0.16, 0.06) * uBeacon * bndl * 0.1 / (bd2 + 0.03);
            // fill from the starfield / lensed light
            float up = 0.5 + 0.5 * n.y;
            col += alb * uFillCol * (0.3 + 0.7 * up);
            // rim: only where the key light comes from behind the silhouette
            float fres = pow(1.0 - clamp(dot(n, V), 0.0, 1.0), 5.0);
            col += uRimCol * fres * smoothstep(-0.3, 0.7, dot(-V, L));
        }
    }
    // beacon (the signal) and ion engine: analytic glows in front of everything
    vec3 bp = beaconP - ro;
    float tb = max(dot(bp, rd), 0.0);
    float db = length(bp - rd * tb) / max(pixAng * tb, 1e-5);   // in pixels
    float beaconVis = tb < tHit + 0.1 ? 1.0 : 0.0;
    glowOut += vec3(1.0, 0.18, 0.08) * uBeacon * beaconVis * (2.2 * exp(-db * db * 0.35) + 0.12 / (1.0 + db * db * 0.02));
    vec3 ep = engineP - ro;
    float te = max(dot(ep, rd), 0.0);
    float de = length(ep - rd * te) / max(pixAng * te, 1e-5);
    // engine only visible from behind
    float eVis = smoothstep(-0.2, 0.3, dot(normalize(ro - engineP), vec3(0, 0, 1)));
    glowOut += vec3(0.45, 0.7, 1.0) * uEngine * eVis * (1.4 * exp(-de * de * 0.12) + 0.08 / (1.0 + de * de * 0.01));
    return vec4(col, cover);
}

// ------------------------------------------------------------- geodesics
struct Trace {
    vec3 col;      // accumulated disk light
    float trans;   // remaining transmittance
    vec3 dir;      // final direction
    float escaped;
};

Trace traceBH(vec3 ro, vec3 rd) {
    Trace tr;
    tr.col = vec3(0.0); tr.trans = 1.0; tr.dir = rd; tr.escaped = 1.0;
    if (uBH < 0.5) return tr;

    vec3 x = ro;
    vec3 v = rd;
    vec3 hv = cross(x, v);
    float h2 = dot(hv, hv);
    float r = length(x);
    vec3 a = -1.5 * h2 * x / (r * r * r * r * r);
    int crossings = 0;
    vec3 haze = vec3(0.0);
    bool captured = false;
    bool done = false;
    for (int i = 0; i < 1000; i++) {
        if (i >= uMaxSteps) { captured = true; break; }
        // step size: proportional to r, finer near the photon sphere and the disk plane
        float dt = uStepK * r;
        dt *= mix(0.5, 1.0, smoothstep(1.3, 2.5, r));
        dt = max(dt, 0.004);
        vec3 vh = v + 0.5 * dt * a;
        vec3 xn = x + dt * vh;
        float rn = length(xn);
        vec3 an = -1.5 * h2 * xn / (rn * rn * rn * rn * rn);
        vec3 vn = vh + 0.5 * dt * an;

        if (uGlow > 0.0) {
            vec3 hz = diskHaze(xn, normalize(vn));
            haze += tr.trans * hz * dt * length(vh);
        }
        // disk plane crossing
        if (x.y * xn.y < 0.0) {
            float t = x.y / (x.y - xn.y);
            vec3 p = mix(x, xn, t);
            float pr = length(p.xz);
            if (pr > uDiskIn && pr < uDiskOut) {
                vec4 ds = diskSample(p, normalize(mix(v, vn, t)), crossings);
                tr.col += tr.trans * ds.rgb * ds.a;
                tr.trans *= 1.0 - ds.a;
                crossings++;
                if (tr.trans < 0.02 || crossings >= 4) { done = true; }
            }
        }
        x = xn; v = vn; a = an; r = rn;
        if (done) break;
        if (r < 1.0) { captured = true; break; }
        if (r > uEscapeR && dot(x, v) > 0.0) break;
    }
    tr.col += haze * uGlow * uDiskGain;
    tr.dir = normalize(v);
    tr.escaped = captured ? 0.0 : 1.0;
    if (done) { tr.escaped = 0.0; tr.trans = 0.0; }
    return tr;
}

void main() {
    vec2 frag = gl_FragCoord.xy + uJitter;
    vec2 p = (frag - 0.5 * uRes) / (0.5 * uRes.y);
    vec3 rd = normalize(uCamRot * vec3(p * uTanHalfFovY, 1.0));
    vec3 ro = uCamPos;

    Trace tr = traceBH(ro, rd);

    // sky through the (possibly bent) final direction
    vec3 fd = tr.dir;
    float fp = max(length(dFdx(fd)), length(dFdy(fd)));
    fp = max(fp, uPixelAngle * 0.3);
    vec3 sky = skyColor(fd, fp);
    vec3 col = tr.col + sky * tr.trans * tr.escaped;

    // probe in the foreground (flat space: it is far from the hole)
    vec3 glow;
    vec4 ship = renderShip(ro, rd, uPixelAngle, glow);
    col = mix(col, ship.rgb, ship.a);
    col += glow;

    fragColor = vec4(max(col, 0.0) * uWeight, uWeight);
}
