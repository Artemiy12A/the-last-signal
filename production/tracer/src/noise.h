// Hash-based 3D gradient noise (improved Perlin style, quintic fade) and fBm with band limiting.
#pragma once
#include <cmath>
#include <cstdint>

inline uint32_t hash3u(int32_t x, int32_t y, int32_t z, uint32_t seed) {
    uint32_t h = seed ^ 0x9E3779B9u;
    h ^= uint32_t(x) * 0x85EBCA6Bu; h = (h << 13) | (h >> 19); h *= 5u; h += 0xE6546B64u;
    h ^= uint32_t(y) * 0xC2B2AE35u; h = (h << 13) | (h >> 19); h *= 5u; h += 0xE6546B64u;
    h ^= uint32_t(z) * 0x27D4EB2Fu; h = (h << 13) | (h >> 19); h *= 5u; h += 0xE6546B64u;
    h ^= h >> 16; h *= 0x85EBCA6Bu; h ^= h >> 13; h *= 0xC2B2AE35u; h ^= h >> 16;
    return h;
}

// Permutation-table gradient noise (Perlin 2002), branchless gradient lookup. The seed becomes a
// large coordinate offset (x, z) and an integer lattice offset (y, applied after the periodic wrap).
struct PermTable {
    uint8_t p[512];
    float g[16][3];
    PermTable() {
        uint32_t st = 0x2545F491u;
        for (int i = 0; i < 256; ++i) p[i] = uint8_t(i);
        for (int i = 255; i > 0; --i) {
            st ^= st << 13; st ^= st >> 17; st ^= st << 5;
            int j = int(st % uint32_t(i + 1));
            uint8_t t = p[i]; p[i] = p[j]; p[j] = t;
        }
        for (int i = 0; i < 256; ++i) p[256 + i] = p[i];
        const float G[16][3] = {{1, 1, 0}, {-1, 1, 0}, {1, -1, 0}, {-1, -1, 0}, {1, 0, 1}, {-1, 0, 1}, {1, 0, -1}, {-1, 0, -1},
                                {0, 1, 1}, {0, -1, 1}, {0, 1, -1}, {0, -1, -1}, {1, 1, 0}, {0, -1, 1}, {-1, 1, 0}, {0, -1, -1}};
        for (int i = 0; i < 16; ++i) for (int k = 0; k < 3; ++k) g[i][k] = G[i][k];
    }
};
inline const PermTable& perm() { static const PermTable T; return T; }

inline float fade(float t) { return t * t * t * (t * (t * 6.f - 15.f) + 10.f); }
inline float lerpf(float a, float b, float t) { return a + (b - a) * t; }

inline void seed_offsets(uint32_t seed, float& ox, float& oz, int32_t& oy) {
    uint32_t h = seed * 0x9E3779B1u + 0x7F4A7C15u;
    h ^= h >> 15; h *= 0x2C1B3C6Du; h ^= h >> 12; h *= 0x297A2D39u; h ^= h >> 15;
    ox = float(h & 0xFFFF) * 0.0137f;
    oz = float((h >> 16) & 0xFFFF) * 0.0173f;
    oy = int32_t((h >> 8) & 0xFF);
}

inline float gnoise_core(float x, float y, float z, int32_t ix, int32_t y0, int32_t y1, int32_t iz) {
    const PermTable& T = perm();
    const uint8_t* P = T.p;
    int X0 = ix & 255, X1 = (ix + 1) & 255, Z0 = iz & 255, Z1 = (iz + 1) & 255;
    int Y0 = y0 & 255, Y1 = y1 & 255;
    int a0 = P[X0] + Y0, a1 = P[X0] + Y1, b0 = P[X1] + Y0, b1 = P[X1] + Y1;
    int h000 = P[P[a0] + Z0] & 15, h001 = P[P[a0] + Z1] & 15;
    int h010 = P[P[a1] + Z0] & 15, h011 = P[P[a1] + Z1] & 15;
    int h100 = P[P[b0] + Z0] & 15, h101 = P[P[b0] + Z1] & 15;
    int h110 = P[P[b1] + Z0] & 15, h111 = P[P[b1] + Z1] & 15;
    auto dg = [&](int h, float dx, float dy, float dz) { return T.g[h][0] * dx + T.g[h][1] * dy + T.g[h][2] * dz; };
    float u = fade(x), v = fade(y), w = fade(z);
    float n000 = dg(h000, x, y, z), n100 = dg(h100, x - 1, y, z);
    float n010 = dg(h010, x, y - 1, z), n110 = dg(h110, x - 1, y - 1, z);
    float n001 = dg(h001, x, y, z - 1), n101 = dg(h101, x - 1, y, z - 1);
    float n011 = dg(h011, x, y - 1, z - 1), n111 = dg(h111, x - 1, y - 1, z - 1);
    return lerpf(lerpf(lerpf(n000, n100, u), lerpf(n010, n110, u), v),
                 lerpf(lerpf(n001, n101, u), lerpf(n011, n111, u), v), w) * 0.9f;
}

// Returns roughly [-1, 1].
inline float gnoise(float x, float y, float z, uint32_t seed) {
    float ox, oz; int32_t oy;
    seed_offsets(seed, ox, oz, oy);
    x += ox; z += oz; y += float(oy);
    float fx = std::floor(x), fy = std::floor(y), fz = std::floor(z);
    int32_t ix = int32_t(fx), iy = int32_t(fy), iz = int32_t(fz);
    return gnoise_core(x - fx, y - fy, z - fz, ix, iy, iy + 1, iz);
}

// Gradient noise periodic in y with integer period py (lattice cells).
inline float gnoise_py(float x, float y, float z, int32_t py, uint32_t seed) {
    float ox, oz; int32_t oy;
    seed_offsets(seed, ox, oz, oy);
    x += ox; z += oz;
    float fx = std::floor(x), fy = std::floor(y), fz = std::floor(z);
    int32_t ix = int32_t(fx), iy = int32_t(fy), iz = int32_t(fz);
    int32_t y0 = ((iy % py) + py) % py, y1 = (y0 + 1) % py;
    return gnoise_core(x - fx, y - fy, z - fz, ix, y0 + oy, y1 + oy, iz);
}

// fBm periodic in y: y is in "cells of octave 0", period py0 cells; lacunarity is exactly 2 so the
// period stays an integer at every octave. footprint is in octave-0 cell units.
inline float fbm_py(float x, float y, float z, int32_t py0, int octaves, float footprint, uint32_t seed,
                    float gain = 0.5f) {
    float sum = 0.f, amp = 0.5f, freq = 1.f;
    int32_t py = py0;
    for (int i = 0; i < octaves; ++i) {
        float feat = 1.0f / freq;
        float fadeo = std::fmin(1.f, std::fmax(0.f, (feat - 1.5f * footprint) / (1.5f * footprint)));
        if (fadeo <= 0.f) break;
        sum += amp * fadeo * gnoise_py(x * freq + 31.7f * i, y * freq, z * freq + 11.3f * i, py, seed + uint32_t(i) * 7919u);
        freq *= 2.f; amp *= gain; py *= 2;
    }
    return sum;
}

// Ridged multifractal, periodic in y: thin bright filaments. Returns ~[0, 1].
inline float ridged_py(float x, float y, float z, int32_t py0, int octaves, float footprint, uint32_t seed,
                       float sharp = 2.0f) {
    float sum = 0.f, norm = 0.f, amp = 1.f, freq = 1.f, weight = 1.f;
    int32_t py = py0;
    for (int i = 0; i < octaves; ++i) {
        float feat = 1.0f / freq;
        float fadeo = std::fmin(1.f, std::fmax(0.f, (feat - 1.5f * footprint) / (1.5f * footprint)));
        if (fadeo <= 0.f) break;
        float n = gnoise_py(x * freq + 13.1f * i, y * freq, z * freq + 7.7f * i, py, seed + uint32_t(i) * 104729u);
        float r = 1.f - std::fabs(n) * 1.4f;
        r = r > 0.f ? r : 0.f;
        r = std::pow(r, sharp) * weight;
        weight = std::fmin(1.f, std::fmax(0.f, r * 1.5f));
        sum += amp * fadeo * r;
        norm += amp;
        freq *= 2.f; amp *= 0.55f; py *= 2;
    }
    return norm > 0 ? sum / norm : 0.f;
}

// fBm with octave count limited by the sampling footprint: `footprint` is the size of one sample
// in the noise's coordinate units; octaves finer than ~2 footprints are faded out (no shimmer).
inline float fbm(float x, float y, float z, int octaves, float footprint, uint32_t seed,
                 float lacunarity = 2.03f, float gain = 0.5f) {
    float sum = 0.f, amp = 0.5f, freq = 1.f;
    for (int i = 0; i < octaves; ++i) {
        float feat = 1.0f / freq;                  // feature size of this octave
        float fadeo = std::fmin(1.f, std::fmax(0.f, (feat - 1.5f * footprint) / (1.5f * footprint)));
        if (fadeo <= 0.f) break;
        float n = gnoise(x * freq, y * freq, z * freq, seed + uint32_t(i) * 1013u);
        sum += amp * n * fadeo;
        freq *= lacunarity; amp *= gain;
        // rotate the domain a little between octaves to hide the lattice
        float nx = 0.8f * x + 0.6f * z, nz = -0.6f * x + 0.8f * z;
        x = nx + 17.3f; z = nz + 5.1f; y += 9.7f;
    }
    return sum;
}

// PCG-style per-pixel random numbers (deterministic across shards).
struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed * 6364136223846793005ULL + 1442695040888963407ULL) { next(); }
    uint32_t next() {
        uint64_t old = s;
        s = old * 6364136223846793005ULL + 1442695040888963407ULL;
        uint32_t xs = uint32_t(((old >> 18u) ^ old) >> 27u);
        uint32_t rot = uint32_t(old >> 59u);
        return (xs >> rot) | (xs << ((-rot) & 31));
    }
    float uni() { return (next() >> 8) * (1.0f / 16777216.0f); }
};
