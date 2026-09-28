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

inline float grad_dot(uint32_t h, float x, float y, float z) {
    // 12 edge directions of a cube (plus 4 repeats), Perlin 2002
    switch (h & 15u) {
        case 0: return x + y;  case 1: return -x + y; case 2: return x - y;  case 3: return -x - y;
        case 4: return x + z;  case 5: return -x + z; case 6: return x - z;  case 7: return -x - z;
        case 8: return y + z;  case 9: return -y + z; case 10: return y - z; case 11: return -y - z;
        case 12: return x + y; case 13: return -y + z; case 14: return -x + y; default: return -y - z;
    }
}

inline float fade(float t) { return t * t * t * (t * (t * 6.f - 15.f) + 10.f); }
inline float lerpf(float a, float b, float t) { return a + (b - a) * t; }

// Returns roughly [-1, 1].
inline float gnoise(float x, float y, float z, uint32_t seed) {
    float fx = std::floor(x), fy = std::floor(y), fz = std::floor(z);
    int32_t ix = int32_t(fx), iy = int32_t(fy), iz = int32_t(fz);
    x -= fx; y -= fy; z -= fz;
    float u = fade(x), v = fade(y), w = fade(z);
    float n000 = grad_dot(hash3u(ix, iy, iz, seed), x, y, z);
    float n100 = grad_dot(hash3u(ix + 1, iy, iz, seed), x - 1, y, z);
    float n010 = grad_dot(hash3u(ix, iy + 1, iz, seed), x, y - 1, z);
    float n110 = grad_dot(hash3u(ix + 1, iy + 1, iz, seed), x - 1, y - 1, z);
    float n001 = grad_dot(hash3u(ix, iy, iz + 1, seed), x, y, z - 1);
    float n101 = grad_dot(hash3u(ix + 1, iy, iz + 1, seed), x - 1, y, z - 1);
    float n011 = grad_dot(hash3u(ix, iy + 1, iz + 1, seed), x, y - 1, z - 1);
    float n111 = grad_dot(hash3u(ix + 1, iy + 1, iz + 1, seed), x - 1, y - 1, z - 1);
    return lerpf(lerpf(lerpf(n000, n100, u), lerpf(n010, n110, u), v),
                 lerpf(lerpf(n001, n101, u), lerpf(n011, n111, u), v), w) * 0.9f;
}

// Gradient noise periodic in y with integer period py (lattice cells).
inline float gnoise_py(float x, float y, float z, int32_t py, uint32_t seed) {
    float fx = std::floor(x), fy = std::floor(y), fz = std::floor(z);
    int32_t ix = int32_t(fx), iy = int32_t(fy), iz = int32_t(fz);
    x -= fx; y -= fy; z -= fz;
    int32_t y0 = ((iy % py) + py) % py, y1 = (y0 + 1) % py;
    float u = fade(x), v = fade(y), w = fade(z);
    float n000 = grad_dot(hash3u(ix, y0, iz, seed), x, y, z);
    float n100 = grad_dot(hash3u(ix + 1, y0, iz, seed), x - 1, y, z);
    float n010 = grad_dot(hash3u(ix, y1, iz, seed), x, y - 1, z);
    float n110 = grad_dot(hash3u(ix + 1, y1, iz, seed), x - 1, y - 1, z);
    float n001 = grad_dot(hash3u(ix, y0, iz + 1, seed), x, y, z - 1);
    float n101 = grad_dot(hash3u(ix + 1, y0, iz + 1, seed), x - 1, y, z - 1);
    float n011 = grad_dot(hash3u(ix, y1, iz + 1, seed), x, y - 1, z - 1);
    float n111 = grad_dot(hash3u(ix + 1, y1, iz + 1, seed), x - 1, y - 1, z - 1);
    return lerpf(lerpf(lerpf(n000, n100, u), lerpf(n010, n110, u), v),
                 lerpf(lerpf(n001, n101, u), lerpf(n011, n111, u), v), w) * 0.9f;
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
