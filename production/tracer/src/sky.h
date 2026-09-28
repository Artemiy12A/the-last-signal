// The sky at infinity: a diffuse Milky Way map (equirectangular, galactic coordinates, mip-mapped)
// and a real star catalogue rendered analytically with flux-conserving lensing footprints.
//
// Galactic unit vector: g = (cos b cos l, cos b sin l, sin b)  (x -> galactic centre, z -> NGP).
// Map convention (NASA SVS Deep Star Maps, galactic): u = 0.5 - l / 2pi (longitude grows to the
// left), v = 0.5 - b / pi.
#pragma once
#include "color.h"
#include <cstdint>
#include <cstdio>
#include <string>
#include <unordered_map>
#include <vector>
#include <cmath>
#include <algorithm>

struct Vec3 {
    double x = 0, y = 0, z = 0;
    Vec3() = default;
    Vec3(double a, double b, double c) : x(a), y(b), z(c) {}
    Vec3 operator+(const Vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
    Vec3 operator-(const Vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
    Vec3 operator*(double s) const { return {x * s, y * s, z * s}; }
    double dot(const Vec3& o) const { return x * o.x + y * o.y + z * o.z; }
    Vec3 cross(const Vec3& o) const { return {y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x}; }
    double len() const { return std::sqrt(x * x + y * y + z * z); }
    Vec3 norm() const { double l = len(); return l > 0 ? *this * (1.0 / l) : *this; }
};

struct Mat3 {
    double m[3][3] = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    Vec3 operator*(const Vec3& v) const {
        return {m[0][0] * v.x + m[0][1] * v.y + m[0][2] * v.z, m[1][0] * v.x + m[1][1] * v.y + m[1][2] * v.z,
                m[2][0] * v.x + m[2][1] * v.y + m[2][2] * v.z};
    }
};

inline void tangent_basis(const Vec3& d, Vec3& e1, Vec3& e2) {
    Vec3 a = std::fabs(d.z) < 0.9 ? Vec3(0, 0, 1) : Vec3(1, 0, 0);
    e1 = a.cross(d).norm();
    e2 = d.cross(e1);
}

// ---------------------------------------------------------------- equirect mip-mapped map
class EquirectMap {
public:
    std::vector<std::vector<RGB>> levels;
    std::vector<int> W, H;
    bool loaded = false;

    void from_pixels(const std::vector<RGB>& px, int w, int h) {
        levels.clear(); W.clear(); H.clear();
        levels.push_back(px); W.push_back(w); H.push_back(h);
        while (W.back() > 4 && H.back() > 2) {
            int pw = W.back(), ph = H.back(), nw = pw / 2, nh = ph / 2;
            std::vector<RGB> n(size_t(nw) * nh);
            const auto& p = levels.back();
            for (int y = 0; y < nh; ++y)
                for (int x = 0; x < nw; ++x) {
                    RGB s = p[size_t(2 * y) * pw + 2 * x] + p[size_t(2 * y) * pw + 2 * x + 1] +
                            p[size_t(2 * y + 1) * pw + 2 * x] + p[size_t(2 * y + 1) * pw + 2 * x + 1];
                    n[size_t(y) * nw + x] = s * 0.25f;
                }
            levels.push_back(std::move(n)); W.push_back(nw); H.push_back(nh);
        }
        loaded = true;
    }

    RGB texel(int lv, int x, int y) const {
        int w = W[lv], h = H[lv];
        x = ((x % w) + w) % w;
        y = std::clamp(y, 0, h - 1);
        return levels[lv][size_t(y) * w + x];
    }
    RGB bilinear(int lv, double u, double v) const {
        double fx = u * W[lv] - 0.5, fy = v * H[lv] - 0.5;
        int x0 = int(std::floor(fx)), y0 = int(std::floor(fy));
        float tx = float(fx - x0), ty = float(fy - y0);
        RGB a = texel(lv, x0, y0), b = texel(lv, x0 + 1, y0), c = texel(lv, x0, y0 + 1), d = texel(lv, x0 + 1, y0 + 1);
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
    }
    // g: galactic unit vector; footprint: angular size (rad) of the sampling kernel
    RGB sample(const Vec3& g, double footprint) const {
        if (!loaded) return RGB();
        double l = std::atan2(g.y, g.x), b = std::asin(std::clamp(g.z, -1.0, 1.0));
        double u = 0.5 - l / (2 * M_PI), v = 0.5 - b / M_PI;
        u -= std::floor(u);
        double texel0 = 2 * M_PI / W[0];
        double lod = std::log2(std::max(footprint, 1e-12) / texel0);
        lod = std::clamp(lod, 0.0, double(levels.size() - 1));
        int l0 = int(lod);
        int l1 = std::min(l0 + 1, int(levels.size()) - 1);
        float t = float(lod - l0);
        RGB a = bilinear(l0, u, v);
        if (t <= 0.f || l1 == l0) return a;
        return a * (1 - t) + bilinear(l1, u, v) * t;
    }
};

// ---------------------------------------------------------------- star catalogue
struct Star {
    float d[3];    // galactic unit vector
    float c[3];    // linear RGB flux (radiance x steradian)
};

class StarField {
public:
    std::vector<Star> stars;              // sorted by cell
    std::unordered_map<uint64_t, std::pair<uint32_t, uint32_t>> cells;
    double cell = 0.0035;                  // cell size in unit-vector (chord) units, ~0.2 deg
    EquirectMap density;                   // all stars splatted (flux / sr), for huge footprints
    bool loaded = false;

    static uint64_t key(int ix, int iy, int iz) {
        return (uint64_t(uint32_t(ix + 1048576)) << 42) | (uint64_t(uint32_t(iy + 1048576)) << 21) |
               uint64_t(uint32_t(iz + 1048576));
    }
    void cell_of(const float* d, int& ix, int& iy, int& iz) const {
        ix = int(std::floor(d[0] / cell)); iy = int(std::floor(d[1] / cell)); iz = int(std::floor(d[2] / cell));
    }

    bool load(const std::string& path, float gain, int density_w = 2048) {
        FILE* f = std::fopen(path.c_str(), "rb");
        if (!f) { std::fprintf(stderr, "stars: cannot open %s\n", path.c_str()); return false; }
        uint32_t n = 0;
        if (std::fread(&n, 4, 1, f) != 1) { std::fclose(f); return false; }
        std::vector<Star> raw(n);
        size_t got = std::fread(raw.data(), sizeof(Star), n, f);
        std::fclose(f);
        if (got != n) { std::fprintf(stderr, "stars: short read\n"); return false; }
        for (auto& s : raw) for (float& c : s.c) c *= gain;
        // sort by cell key
        std::vector<std::pair<uint64_t, uint32_t>> ks(n);
        for (uint32_t i = 0; i < n; ++i) {
            int ix, iy, iz; cell_of(raw[i].d, ix, iy, iz);
            ks[i] = {key(ix, iy, iz), i};
        }
        std::sort(ks.begin(), ks.end());
        stars.resize(n);
        cells.reserve(n);
        for (uint32_t i = 0; i < n; ++i) {
            stars[i] = raw[ks[i].second];
            auto it = cells.find(ks[i].first);
            if (it == cells.end()) cells.emplace(ks[i].first, std::make_pair(i, 1u));
            else it->second.second++;
        }
        // density map (flux per steradian)
        int w = density_w, h = density_w / 2;
        std::vector<RGB> px(size_t(w) * h);
        for (const Star& s : stars) {
            double l = std::atan2(s.d[1], s.d[0]), b = std::asin(std::clamp<double>(s.d[2], -1, 1));
            double u = 0.5 - l / (2 * M_PI), v = 0.5 - b / M_PI;
            u -= std::floor(u);
            int x = std::min(w - 1, int(u * w)), y = std::clamp(int(v * h), 0, h - 1);
            double lat0 = M_PI / 2 - M_PI * y / h, lat1 = M_PI / 2 - M_PI * (y + 1) / h;
            double sr = (2 * M_PI / w) * (std::sin(lat0) - std::sin(lat1));
            px[size_t(y) * w + x] += RGB(s.c[0], s.c[1], s.c[2]) * float(1.0 / sr);
        }
        density.from_pixels(px, w, h);
        loaded = true;
        std::fprintf(stderr, "stars: %u stars in %zu cells\n", n, cells.size());
        return true;
    }

    // Sum of star radiance for a pixel whose sky footprint around galactic direction g has
    // covariance S (2x2, in the tangent basis e1,e2 of g, rad^2). Flux-conserving Gaussian filter.
    RGB eval(const Vec3& g, const Vec3& e1, const Vec3& e2, double s11, double s12, double s22,
             double max_radius) const {
        if (!loaded) return RGB();
        double det = s11 * s22 - s12 * s12;
        double tr = s11 + s22;
        double lmax = 0.5 * tr + std::sqrt(std::max(0.0, 0.25 * tr * tr - det));
        double R = 3.5 * std::sqrt(std::max(lmax, 0.0));
        RGB tex;
        float wtex = 0.f;
        if (R > 0.5 * max_radius) {
            // footprint too large for individual stars: use the splatted density map
            wtex = float(std::clamp((R - 0.5 * max_radius) / (0.5 * max_radius), 0.0, 1.0));
            tex = density.sample(g, 2.0 * std::sqrt(lmax));
            if (wtex >= 1.f) return tex;
        }
        if (det <= 1e-40) return tex * wtex;
        double i11 = s22 / det, i12 = -s12 / det, i22 = s11 / det;
        double norm = 1.0 / (2 * M_PI * std::sqrt(det));
        RGB sum;
        int r = int(std::ceil(R / cell));
        float gd[3] = {float(g.x), float(g.y), float(g.z)};
        int cx, cy, cz; cell_of(gd, cx, cy, cz);
        double R2 = R * R;
        for (int ix = cx - r; ix <= cx + r; ++ix)
            for (int iy = cy - r; iy <= cy + r; ++iy)
                for (int iz = cz - r; iz <= cz + r; ++iz) {
                    // skip cells whose box can't touch the sphere near g
                    auto it = cells.find(key(ix, iy, iz));
                    if (it == cells.end()) continue;
                    uint32_t s0 = it->second.first, sn = it->second.second;
                    for (uint32_t k = s0; k < s0 + sn; ++k) {
                        const Star& st = stars[k];
                        double dx = st.d[0] - g.x, dy = st.d[1] - g.y, dz = st.d[2] - g.z;
                        if (dx * dx + dy * dy + dz * dz > R2) continue;
                        double u = dx * e1.x + dy * e1.y + dz * e1.z;
                        double v = dx * e2.x + dy * e2.y + dz * e2.z;
                        double q = i11 * u * u + 2 * i12 * u * v + i22 * v * v;
                        if (q > 12.25) continue;
                        float w = float(norm * std::exp(-0.5 * q));
                        sum += RGB(st.c[0], st.c[1], st.c[2]) * w;
                    }
                }
        return sum * (1.f - wtex) + tex * wtex;
    }
};
