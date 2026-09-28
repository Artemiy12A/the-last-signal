// THE LAST SIGNAL — Kerr black hole renderer.
//
//   tracer scene.json
//
// Renders one frame described by a JSON scene file into a multi-layer EXR:
//   disk.RGB   accretion disk and plunging gas (attenuated)
//   haze.RGB   faint gas above/below the disk (attenuated)
//   sky.RGB    diffuse Milky Way, lensed (attenuated)
//   stars.RGB  catalogue stars, lensed, flux-conserving (attenuated)
//   A          fraction of the background blocked by gas or the hole (1 - transmittance)
//   hole       fraction of samples captured by the horizon
// beauty = disk + haze + sky + stars.
//
// Two passes: (A) a geometry-only grid of rays through the pixel corners gives each pixel's
// footprint on the celestial sphere (lensing Jacobian) for filtering stars and the sky map;
// (B) pixels touching the gas or the horizon are supersampled with jittered position and
// shutter time (motion blur), integrating emission and absorption along the geodesic.
#define TINYEXR_IMPLEMENTATION
#define TINYEXR_USE_MINIZ 1
#include "../third_party/miniz.h"
#include "../third_party/tinyexr.h"
#include "../third_party/json.hpp"

#include "color.h"
#include "disk.h"
#include "kerr.h"
#include "noise.h"
#include "sky.h"

#include <omp.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

using json = nlohmann::json;

// ---------------------------------------------------------------- small math
struct Quat {
    double w = 1, x = 0, y = 0, z = 0;
};
static Quat quat_from_basis(const Vec3& r, const Vec3& u, const Vec3& f) {
    // columns r,u,f of a rotation matrix
    double m00 = r.x, m01 = u.x, m02 = f.x, m10 = r.y, m11 = u.y, m12 = f.y, m20 = r.z, m21 = u.z, m22 = f.z;
    Quat q;
    double tr = m00 + m11 + m22;
    if (tr > 0) {
        double s = std::sqrt(tr + 1.0) * 2;
        q.w = 0.25 * s; q.x = (m21 - m12) / s; q.y = (m02 - m20) / s; q.z = (m10 - m01) / s;
    } else if (m00 > m11 && m00 > m22) {
        double s = std::sqrt(1.0 + m00 - m11 - m22) * 2;
        q.w = (m21 - m12) / s; q.x = 0.25 * s; q.y = (m01 + m10) / s; q.z = (m02 + m20) / s;
    } else if (m11 > m22) {
        double s = std::sqrt(1.0 + m11 - m00 - m22) * 2;
        q.w = (m02 - m20) / s; q.x = (m01 + m10) / s; q.y = 0.25 * s; q.z = (m12 + m21) / s;
    } else {
        double s = std::sqrt(1.0 + m22 - m00 - m11) * 2;
        q.w = (m10 - m01) / s; q.x = (m02 + m20) / s; q.y = (m12 + m21) / s; q.z = 0.25 * s;
    }
    return q;
}
static Quat qslerp(Quat a, Quat b, double t) {
    double d = a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z;
    if (d < 0) { b = {-b.w, -b.x, -b.y, -b.z}; d = -d; }
    double wa, wb;
    if (d > 0.9995) { wa = 1 - t; wb = t; }
    else { double th = std::acos(d), s = std::sin(th); wa = std::sin((1 - t) * th) / s; wb = std::sin(t * th) / s; }
    Quat q{wa * a.w + wb * b.w, wa * a.x + wb * b.x, wa * a.y + wb * b.y, wa * a.z + wb * b.z};
    double n = std::sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
    return {q.w / n, q.x / n, q.y / n, q.z / n};
}
static void quat_basis(const Quat& q, Vec3& r, Vec3& u, Vec3& f) {
    double w = q.w, x = q.x, y = q.y, z = q.z;
    r = {1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)};
    u = {2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)};
    f = {2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)};
}

static Vec3 jvec(const json& j) { return Vec3(j[0].get<double>(), j[1].get<double>(), j[2].get<double>()); }

// ---------------------------------------------------------------- camera
struct CamPose {
    Vec3 pos, right, up, fwd;
    Vec3 vel;  // velocity relative to the static observer, fraction of c, world axes
    Quat q;
};

struct Tetrad {
    double u[4];       // observer 4-velocity (contravariant)
    double e[3][4];    // spatial legs: right, up, forward (contravariant)
    Vec3 pos;
};

static double g_a = 0.9;
static bool g_debug = false;
static std::atomic<long> g_steps{0}, g_evals{0}, g_rays{0};

// Static observer (Killing time) at pos, boosted by velocity vel; spatial legs aligned as closely
// as possible with the requested Euclidean camera axes.
static Tetrad make_tetrad(const CamPose& cp) {
    double g[4][4];
    ks_metric(cp.pos.x, cp.pos.y, cp.pos.z, g_a, g);
    Tetrad T;
    T.pos = cp.pos;
    double u[4] = {1, 0, 0, 0};
    double n = -mdot(g, u, u);
    if (n <= 1e-6) n = 1e-6;  // inside the ergosphere a static observer does not exist
    for (double& c : u) c /= std::sqrt(n);
    Vec3 axes[3] = {cp.fwd, cp.up, cp.right};
    double E[3][4];
    for (int i = 0; i < 3; ++i) {
        double v[4] = {0, axes[i].x, axes[i].y, axes[i].z};
        // project out u and previous legs (Gram-Schmidt in the metric)
        double vu = mdot(g, v, u);
        for (int m = 0; m < 4; ++m) v[m] += vu * u[m];
        for (int j = 0; j < i; ++j) {
            double vj = mdot(g, v, E[j]);
            for (int m = 0; m < 4; ++m) v[m] -= vj * E[j][m];
        }
        double l = std::sqrt(std::max(mdot(g, v, v), 1e-30));
        for (int m = 0; m < 4; ++m) E[i][m] = v[m] / l;
    }
    // E[0]=fwd, E[1]=up, E[2]=right. Handedness check: right should be fwd x up in world terms.
    for (int m = 0; m < 4; ++m) {
        T.e[2][m] = E[0][m];  // forward
        T.e[1][m] = E[1][m];  // up
        T.e[0][m] = E[2][m];  // right
        T.u[m] = u[m];
    }
    // boost
    Vec3 b = cp.vel;
    double beta2 = b.dot(b);
    if (beta2 > 1e-12) {
        // velocity components in the static frame's legs
        double bl[3] = {b.dot(cp.right), b.dot(cp.up), b.dot(cp.fwd)};
        double bb = std::sqrt(bl[0] * bl[0] + bl[1] * bl[1] + bl[2] * bl[2]);
        if (bb > 0.999) { for (double& c : bl) c *= 0.999 / bb; bb = 0.999; }
        double gam = 1.0 / std::sqrt(1 - bb * bb);
        double nb[3] = {bl[0] / bb, bl[1] / bb, bl[2] / bb};
        double U[4], Eb[3][4];
        for (int m = 0; m < 4; ++m) {
            double bv = bl[0] * T.e[0][m] + bl[1] * T.e[1][m] + bl[2] * T.e[2][m];
            U[m] = gam * (T.u[m] + bv);
        }
        for (int i = 0; i < 3; ++i)
            for (int m = 0; m < 4; ++m) {
                double nv = nb[0] * T.e[0][m] + nb[1] * T.e[1][m] + nb[2] * T.e[2][m];
                // Lorentz boost of spatial leg i: e_i' = e_i + (gam-1) n_i n + gam beta_i u
                Eb[i][m] = T.e[i][m] + (gam - 1) * nb[i] * nv + gam * bl[i] * T.u[m];
            }
        for (int m = 0; m < 4; ++m) { T.u[m] = U[m]; for (int i = 0; i < 3; ++i) T.e[i][m] = Eb[i][m]; }
    }
    return T;
}

// ---------------------------------------------------------------- relativistic beacon
// An emitter (the ship's strobe) moving on a precomputed timelike worldline. Rays pick it up at
// the coordinate time they pass it (light-travel delays, multiple lensed images and echoes come
// out naturally); its colour and brightness follow the redshift g = 1 / (k . u_beacon).
struct Beacon {
    bool on = false;
    std::vector<double> t, x, y, z, ut, ux, uy, uz, tau;   // table in coordinate time (ascending)
    double t_cam = 0, t_span = 0;                         // camera coordinate time, shutter span
    double sigma = 0.05, intensity = 1.0, T_emit = 9000, p_g = 4.0, decay = 0.05, steady = 0.0;
    std::vector<std::pair<double, double>> pulses;        // (tau_start, duration) proper time
    bool at(double tq, double pos[3], double u[4], double& tq_tau) const {
        if (!on || t.size() < 2 || tq < t.front() || tq > t.back()) return false;
        size_t i = std::upper_bound(t.begin(), t.end(), tq) - t.begin();
        i = std::clamp<size_t>(i, 1, t.size() - 1);
        double f = (tq - t[i - 1]) / std::max(t[i] - t[i - 1], 1e-12);
        auto L = [&](const std::vector<double>& v) { return v[i - 1] * (1 - f) + v[i] * f; };
        pos[0] = L(x); pos[1] = L(y); pos[2] = L(z);
        u[0] = L(ut); u[1] = L(ux); u[2] = L(uy); u[3] = L(uz);
        tq_tau = L(tau);
        return true;
    }
    double envelope(double ta) const {
        double v = steady;
        for (auto& p : pulses) {
            double d = ta - p.first;
            if (d < 0) continue;
            double e = d < p.second ? 1.0 : std::exp(-(d - p.second) / decay);
            v = std::max(v, e);
        }
        return v;
    }
};

// ---------------------------------------------------------------- scene
struct Scene {
    int W = 640, H = 268;
    double hfov = 40.0 * M_PI / 180;
    std::string projection = "rect";
    CamPose cam0, cam1;
    double time = 0, shutter_dt = 0;
    int spp = 16, spp_haze = 2, star_times = 1;
    double hfac = 0.12, far_boost = 100.0, escape_r = 3000.0;
    bool light_delay = true;
    double pixel_sigma = 0.45;
    double ds_scale = 3.0;
    int spp_min = 4;
    double var_thresh = 0.02;
    DiskParams disk;
    bool disk_on = true;
    Mat3 sky_rot;
    std::string sky_path, stars_path;
    double sky_gain = 1.0, stars_gain = 1.0, star_max_radius = 0.006;
    double sky_doppler = 1.0;
    std::string out = "out.exr";
    int crop[4] = {0, 0, -1, -1};
    Beacon beacon;
    int threads = 0;
    uint32_t seed = 1;
    double white_K = 6500;
};

static CamPose read_pose(const json& j) {
    CamPose c;
    c.pos = jvec(j["pos"]);
    c.fwd = jvec(j["fwd"]).norm();
    Vec3 up = jvec(j.value("up", json::array({0, 0, 1})));
    c.right = c.fwd.cross(up).norm();
    c.up = c.right.cross(c.fwd).norm();
    if (j.contains("vel")) c.vel = jvec(j["vel"]);
    c.q = quat_from_basis(c.right, c.up, c.fwd * -1.0);  // (right, up, back) is right-handed
    return c;
}

static CamPose pose_at(const Scene& S, double u) {
    CamPose c;
    c.pos = S.cam0.pos * (1 - u) + S.cam1.pos * u;
    c.vel = S.cam0.vel * (1 - u) + S.cam1.vel * u;
    c.q = qslerp(S.cam0.q, S.cam1.q, u);
    quat_basis(c.q, c.right, c.up, c.fwd);
    c.fwd = c.fwd * -1.0;
    return c;
}

// local camera-frame direction (right, up, forward components) for image-plane point (px, py)
static Vec3 local_dir(const Scene& S, double px, double py) {
    if (S.projection == "equirect") {
        double lon = (px / S.W - 0.5) * 2 * M_PI, lat = (0.5 - py / S.H) * M_PI;
        return Vec3(std::cos(lat) * std::sin(lon), std::sin(lat), std::cos(lat) * std::cos(lon));
    }
    if (S.projection == "world_equirect") {
        // Blender/Cycles equirect convention in world axes (Z up): u -> azimuth, v -> elevation
        double az = (0.5 - px / S.W) * 2 * M_PI, el = (0.5 - py / S.H) * M_PI;
        return Vec3(std::cos(el) * std::cos(az), std::cos(el) * std::sin(az), std::sin(el));  // world!
    }
    double t = std::tan(0.5 * S.hfov);
    double sx = (2 * px / S.W - 1) * t;
    double sy = (1 - 2 * py / S.H) * t * double(S.H) / S.W;
    return Vec3(sx, sy, 1.0).norm();
}

// Initial photon (back-traced, past-directed) for a local direction n in the camera frame.
static void launch(const Scene& S, const Tetrad& T, const CamPose& cp, const Vec3& n_local, Photon& ph, double& kt) {
    double kv[4];
    Vec3 n = n_local;
    if (S.projection == "world_equirect") {
        // n is in world axes; convert to the tetrad legs
        n = Vec3(n.dot(cp.right), n.dot(cp.up), n.dot(cp.fwd));
    }
    // back-traced k = -p = -u + n^i e_i  (observer measures E = 1)
    for (int m = 0; m < 4; ++m) kv[m] = -T.u[m] + n.x * T.e[0][m] + n.y * T.e[1][m] + n.z * T.e[2][m];
    double g[4][4];
    ks_metric(T.pos.x, T.pos.y, T.pos.z, g_a, g);
    double kc[4];
    for (int m = 0; m < 4; ++m) { kc[m] = 0; for (int q = 0; q < 4; ++q) kc[m] += g[m][q] * kv[q]; }
    ph.x[0] = T.pos.x; ph.x[1] = T.pos.y; ph.x[2] = T.pos.z;
    ph.k[0] = kc[1]; ph.k[1] = kc[2]; ph.k[2] = kc[3];
    ph.t = 0;
    kt = kc[0];
}

struct TraceResult {
    bool escaped = false;
    Vec3 dir;              // world escape direction
    double g_inf = 1.0;    // observed / emitted energy for light from infinity
    bool touched = false;  // entered the dense disk slab
    bool hazed = false;    // passed through the haze region
    double rmin = 1e30;
    RGB disk, haze, beacon;
    float T = 1.f;         // transmittance through the gas
};

struct Tracer {
    const Scene* S;
    const BlackbodyLUT* bb = nullptr;
    const DiskModel* D;
    double rp, rcap;

    void trace(Photon ph, double kt, bool shade, double time, double pix_angle, Rng* rng, TraceResult& R) const {
        const double a = g_a;
        PhotonDeriv d0, d1;
        photon_rhs(ph, kt, a, d0);
        double path = 0;
        double r = ks_radius(ph.x[0], ph.x[1], ph.x[2], a);
        double rprev = r + 1;
        double Rext = S->disk_on ? D->r_extent() : -1;
        struct Cnt { long n = 0; ~Cnt() { g_steps += n; g_rays += 1; } } cnt;
        for (int n = 0; n < 20000; ++n) {
            cnt.n = n;
            R.rmin = std::min(R.rmin, r);
            if (g_debug && (n % 10 == 0)) std::fprintf(stderr, "  n=%d r=%.4f x=(%.3f %.3f %.3f) k=(%.3f %.3f %.3f) kt=%.4f\n", n, r, ph.x[0], ph.x[1], ph.x[2], ph.k[0], ph.k[1], ph.k[2], kt);
            if (r < rp * 1.01 || (r < rcap && r < rprev)) { R.escaped = false; R.T = shade ? R.T : R.T; return; }
            double sp = std::sqrt(d0.dx[0] * d0.dx[0] + d0.dx[1] * d0.dx[1] + d0.dx[2] * d0.dx[2]);
            if (sp > 1e5) { R.escaped = false; return; }
            double rdot = ph.x[0] * d0.dx[0] + ph.x[1] * d0.dx[1] + ph.x[2] * d0.dx[2];
            if (r > S->escape_r && rdot > 0) {
                R.escaped = true;
                R.dir = Vec3(d0.dx[0], d0.dx[1], d0.dx[2]).norm();
                R.g_inf = 1.0 / kt;
                return;
            }
            double h = step_size(r, rp, sp, S->hfac, S->far_boost);
            // near the gas, keep steps short enough for a good Hermite interpolation
            bool near_gas = S->disk_on && r < Rext * 1.05;
            if (near_gas) h = std::min(h, 0.35 * std::max(r - rp, 0.2) / sp);
            Photon p0 = ph;
            // RK4 reusing d0
            {
                PhotonDeriv k2, k3, k4;
                Photon tmp;
                auto add = [&](const PhotonDeriv& d, double c) {
                    Photon o;
                    for (int i = 0; i < 3; ++i) { o.x[i] = p0.x[i] + c * d.dx[i]; o.k[i] = p0.k[i] + c * d.dk[i]; }
                    o.t = p0.t + c * d.dt;
                    return o;
                };
                tmp = add(d0, 0.5 * h); photon_rhs(tmp, kt, a, k2);
                tmp = add(k2, 0.5 * h); photon_rhs(tmp, kt, a, k3);
                tmp = add(k3, h); photon_rhs(tmp, kt, a, k4);
                const double h6 = h / 6.0;
                for (int i = 0; i < 3; ++i) {
                    ph.x[i] += h6 * (d0.dx[i] + 2 * k2.dx[i] + 2 * k3.dx[i] + k4.dx[i]);
                    ph.k[i] += h6 * (d0.dk[i] + 2 * k2.dk[i] + 2 * k3.dk[i] + k4.dk[i]);
                }
                ph.t += h6 * (d0.dt + 2 * k2.dt + 2 * k3.dt + k4.dt);
            }
            photon_rhs(ph, kt, a, d1);
            double r1 = ks_radius(ph.x[0], ph.x[1], ph.x[2], a);
            double chord = std::sqrt((ph.x[0] - p0.x[0]) * (ph.x[0] - p0.x[0]) + (ph.x[1] - p0.x[1]) * (ph.x[1] - p0.x[1]) +
                                     (ph.x[2] - p0.x[2]) * (ph.x[2] - p0.x[2]));
            // ---- gas along this segment
            if (near_gas && (r < Rext || r1 < Rext)) {
                double zmax0 = D->z_extent(r), zmax1 = D->z_extent(r1);
                bool cross = (p0.x[2] > 0) != (ph.x[2] > 0);
                bool inside = std::fabs(p0.x[2]) < zmax0 || std::fabs(ph.x[2]) < zmax1 || cross;
                if (inside) {
                    R.hazed = true;
                    bool slab = D->in_slab(r, p0.x[2]) || D->in_slab(r1, ph.x[2]) || (cross && std::min(r, r1) < D->P.r_out * 1.25);
                    if (slab) R.touched = true;
                    if (shade && R.T > 1e-3f) {
                        if (slab) march(p0, d0, ph, d1, h, kt, time, pix_angle, path, chord, rng, R);
                        else haze_segment(p0, ph, kt, time, chord, rng, R);
                    }
                }
            }
            if (shade && S->beacon.on) beacon_segment(p0, ph, kt, time, R);
            path += chord;
            d0 = d1;
            rprev = r;
            r = r1;
        }
        R.escaped = false;
    }

    void beacon_segment(const Photon& p0, const Photon& p1, double kt, double time, TraceResult& R) const {
        const Beacon& B = S->beacon;
        // `time` carries the sample's shutter offset relative to the disk clock; map it onto the
        // beacon's clock through the shutter span
        double tshift = (S->shutter_dt > 0) ? (time - S->time) / S->shutter_dt * B.t_span : 0.0;
        double tq = B.t_cam + tshift + 0.5 * (p0.t + p1.t);
        double bp[3], bu[4], btau;
        if (!B.at(tq, bp, bu, btau)) return;
        double d[3] = {p1.x[0] - p0.x[0], p1.x[1] - p0.x[1], p1.x[2] - p0.x[2]};
        double w[3] = {bp[0] - p0.x[0], bp[1] - p0.x[1], bp[2] - p0.x[2]};
        double dd = d[0] * d[0] + d[1] * d[1] + d[2] * d[2];
        double sp = std::clamp((w[0] * d[0] + w[1] * d[1] + w[2] * d[2]) / std::max(dd, 1e-30), 0.0, 1.0);
        double c[3] = {p0.x[0] + sp * d[0] - bp[0], p0.x[1] + sp * d[1] - bp[1], p0.x[2] + sp * d[2] - bp[2]};
        double r2 = c[0] * c[0] + c[1] * c[1] + c[2] * c[2];
        if (r2 > 36.0 * B.sigma * B.sigma) return;
        double env = B.envelope(btau);
        if (env <= 0) return;
        double k[3] = {p0.k[0] * (1 - sp) + p1.k[0] * sp, p0.k[1] * (1 - sp) + p1.k[1] * sp, p0.k[2] * (1 - sp) + p1.k[2] * sp};
        double kdu = kt * bu[0] + k[0] * bu[1] + k[1] * bu[2] + k[2] * bu[3];
        double g = std::clamp(1.0 / std::max(kdu, 1e-9), 1e-4, 50.0);
        double I = B.intensity * env * std::pow(g, B.p_g) * std::exp(-0.5 * r2 / (B.sigma * B.sigma));
        R.beacon += (*bb)(B.T_emit * g) * float(I * R.T);
    }

    // Outside the dense slab only the smooth haze remains: one jittered sample per segment.
    void haze_segment(const Photon& p0, const Photon& p1, double kt, double time, double chord, Rng* rng,
                      TraceResult& R) const {
        double s = rng ? rng->uni() : 0.5;
        double x[3], k[3];
        for (int i = 0; i < 3; ++i) { x[i] = p0.x[i] * (1 - s) + p1.x[i] * s; k[i] = p0.k[i] * (1 - s) + p1.k[i] * s; }
        double tm = time + (S->light_delay ? (p0.t * (1 - s) + p1.t * s) : 0.0);
        DiskModel::Sample smp;
        D->eval(x[0], x[1], x[2], kt, k, tm, 1.0, smp);
        R.haze += smp.emit_haze * (R.T * float(chord));
        if (smp.alpha > 0) {
            float att = std::exp(-smp.alpha * float(chord));
            R.disk += smp.emit_disk * (R.T * (1 - att) / smp.alpha);
            R.T *= att;
        }
    }

    // Emission/absorption along one RK segment, Hermite-interpolated.
    void march(const Photon& p0, const PhotonDeriv& d0, const Photon& p1, const PhotonDeriv& d1, double h, double kt,
               double time, double pix_angle, double path0, double chord, Rng* rng, TraceResult& R) const {
        const DiskModel& Dm = *D;
        double s = 0;
        double jitter = rng ? rng->uni() : 0.5;
        bool first = true;
        while (s < 1.0 && R.T > 1e-3f) {
            // position at s
            double s2 = s * s, s3 = s2 * s;
            double h00 = 2 * s3 - 3 * s2 + 1, h10 = s3 - 2 * s2 + s, h01 = -2 * s3 + 3 * s2, h11 = s3 - s2;
            double x[3], k[3];
            for (int i = 0; i < 3; ++i) {
                x[i] = h00 * p0.x[i] + h10 * h * d0.dx[i] + h01 * p1.x[i] + h11 * h * d1.dx[i];
                k[i] = p0.k[i] * (1 - s) + p1.k[i] * s;
            }
            double r = ks_radius(x[0], x[1], x[2], g_a);
            double H = Dm.scale_height(std::max(r, Dm.P.r_in));
            double az = std::fabs(x[2]);
            // local step: dense near the midplane, sparse above it
            double ds = S->ds_scale * std::max(0.3 * H, 0.45 * (az - 2.5 * H));
            if (Dm.P.haze > 0) ds = std::min(ds, 0.6 * Dm.P.haze_h * r);
            ds = std::clamp(ds, 0.004, 2.0);
            double dsn = ds / std::max(chord, 1e-9);  // in s units
            if (first) { s += dsn * jitter; first = false; if (s >= 1.0) break; continue; }
            double foot = pix_angle * (path0 + s * chord) + 0.5 * ds;
            double tm = time;
            if (S->light_delay) tm += (p0.t * (1 - s) + p1.t * s);
            DiskModel::Sample smp;
            g_evals.fetch_add(1, std::memory_order_relaxed);
            Dm.eval(x[0], x[1], x[2], kt, k, tm, foot, smp);
            if (smp.alpha > 0 || smp.emit_haze.lum() > 0) {
                float tau = smp.alpha * float(ds);
                float att = std::exp(-tau);
                // exact integral of constant source over the step: S * (1 - e^-tau)
                if (smp.alpha > 1e-6f) R.disk += smp.emit_disk * (R.T * (1 - att) / smp.alpha);
                else R.disk += smp.emit_disk * (R.T * float(ds));
                R.haze += smp.emit_haze * (R.T * float(ds));
                R.T *= att;
            }
            s += dsn * (rng ? (0.5 + rng->uni()) : 1.0);
        }
    }
};

// ---------------------------------------------------------------- main
int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: tracer scene.json\n"); return 1; }
    json J;
    { std::ifstream f(argv[1]); if (!f) { std::fprintf(stderr, "cannot open %s\n", argv[1]); return 1; } f >> J; }
    Scene S;
    S.W = J.value("width", 640); S.H = J.value("height", 268);
    S.hfov = J.value("hfov_deg", 40.0) * M_PI / 180;
    S.projection = J.value("projection", std::string("rect"));
    S.cam0 = read_pose(J["cam"][0]);
    S.cam1 = J["cam"].size() > 1 ? read_pose(J["cam"][1]) : S.cam0;
    S.time = J.value("time", 0.0); S.shutter_dt = J.value("shutter_dt", 0.0);
    S.spp = J.value("spp", 16); S.spp_haze = J.value("spp_haze", 2); S.star_times = J.value("star_times", 1);
    S.hfac = J.value("hfac", 0.12); S.far_boost = J.value("far_boost", 100.0);
    S.escape_r = J.value("escape_r", 3000.0);
    S.light_delay = J.value("light_delay", true);
    S.pixel_sigma = J.value("pixel_sigma", 0.45);
    S.ds_scale = J.value("ds_scale", 3.0);
    S.spp_min = J.value("spp_min", 4);
    S.var_thresh = J.value("var_thresh", 0.02);
    S.out = J.value("out", std::string("out.exr"));
    S.threads = J.value("threads", 0);
    S.seed = J.value("seed", 1u);
    S.white_K = J.value("white_K", 6500.0);
    g_a = J.value("spin", 0.9);
    if (J.contains("crop")) for (int i = 0; i < 4; ++i) S.crop[i] = J["crop"][i];
    if (S.crop[2] < 0) { S.crop[2] = S.W; S.crop[3] = S.H; }

    BlackbodyLUT bb;
    bb.build(S.white_K);
    DiskModel D;
    S.disk_on = J.contains("disk") && J["disk"].value("on", true);
    if (J.contains("disk")) {
        const json& d = J["disk"];
        DiskParams& p = S.disk;
        p.a = g_a;
#define DP(name) p.name = d.value(#name, p.name)
        DP(r_in); DP(r_out); DP(h_over_r); DP(flare); DP(T_peak); DP(kappa); DP(emit_gain); DP(p_T); DP(p_g);
        DP(color_g); DP(flow_period); DP(k_ln); DP(n_phi); DP(z_cells); DP(octaves); DP(turb); DP(warp);
        DP(arms); DP(hot_spots); DP(plunge); DP(haze); DP(haze_h); DP(haze_gain); DP(inner_soft); DP(rim); DP(seed);
        DP(sigma_slope); DP(taper); DP(temp_var); DP(lanes); DP(filaments); DP(fil_sharp); DP(fil_scale); DP(floor_dens);
#undef DP
    }
    D.init(S.disk, &bb);

    // sky
    EquirectMap sky;
    StarField stars;
    if (J.contains("sky")) {
        const json& s = J["sky"];
        if (s.contains("rot")) for (int i = 0; i < 3; ++i) for (int j = 0; j < 3; ++j) S.sky_rot.m[i][j] = s["rot"][i][j];
        S.sky_gain = s.value("gain", 1.0);
        S.stars_gain = s.value("stars_gain", 1.0);
        S.star_max_radius = s.value("star_max_radius", 0.006);
        S.sky_doppler = s.value("doppler", 1.0);
        std::string mw = s.value("map", std::string());
        if (!mw.empty()) {
            float* rgba = nullptr; int w, h; const char* err = nullptr;
            if (LoadEXR(&rgba, &w, &h, mw.c_str(), &err) != TINYEXR_SUCCESS) {
                std::fprintf(stderr, "sky map %s: %s\n", mw.c_str(), err ? err : "?");
                if (err) FreeEXRErrorMessage(err);
            } else {
                std::vector<RGB> px(size_t(w) * h);
                for (size_t i = 0; i < px.size(); ++i)
                    px[i] = RGB(rgba[4 * i], rgba[4 * i + 1], rgba[4 * i + 2]) * float(S.sky_gain);
                free(rgba);
                sky.from_pixels(px, w, h);
            }
        }
        std::string st = s.value("stars", std::string());
        if (!st.empty()) stars.load(st, float(S.stars_gain));
    }

    if (S.threads > 0) omp_set_num_threads(S.threads);
    if (argc >= 5 && std::string(argv[2]) == "--debug") {
        g_debug = true;
        CamPose cp = pose_at(S, 0.5);
        Tetrad T = make_tetrad(cp);
        std::fprintf(stderr, "cam pos (%.3f %.3f %.3f) fwd (%.3f %.3f %.3f)\n", cp.pos.x, cp.pos.y, cp.pos.z, cp.fwd.x, cp.fwd.y, cp.fwd.z);
        std::fprintf(stderr, "u = (%.4f %.4f %.4f %.4f)\n", T.u[0], T.u[1], T.u[2], T.u[3]);
        for (int i = 0; i < 3; ++i) std::fprintf(stderr, "e%d = (%.4f %.4f %.4f %.4f)\n", i, T.e[i][0], T.e[i][1], T.e[i][2], T.e[i][3]);
        Photon ph; double kt;
        Vec3 n = local_dir(S, atof(argv[3]), atof(argv[4]));
        launch(S, T, cp, n, ph, kt);
        Tracer TR0; TR0.S = &S; TR0.D = &D; TR0.bb = &bb; TR0.rp = horizon_radius(g_a); TR0.rcap = photon_orbit_prograde(g_a);
        TraceResult R;
        TR0.trace(ph, kt, false, 0, 1e-3, nullptr, R);
        std::fprintf(stderr, "escaped %d dir (%.3f %.3f %.3f) touched %d rmin %.3f\n", R.escaped, R.dir.x, R.dir.y, R.dir.z, R.touched, R.rmin);
        return 0;
    }
    auto t0 = std::chrono::steady_clock::now();

    if (J.contains("beacon")) {
        const json& b = J["beacon"];
        Beacon& B = S.beacon;
        B.on = b.value("on", true);
        const json& tb = b["table"];   // rows: [t, x, y, z, ut, ux, uy, uz, tau]
        for (const auto& row : tb) {
            B.t.push_back(row[0]); B.x.push_back(row[1]); B.y.push_back(row[2]); B.z.push_back(row[3]);
            B.ut.push_back(row[4]); B.ux.push_back(row[5]); B.uy.push_back(row[6]); B.uz.push_back(row[7]);
            B.tau.push_back(row[8]);
        }
        B.t_cam = b.value("t_cam", 0.0); B.t_span = b.value("t_span", 0.0);
        B.sigma = b.value("sigma", 0.05); B.intensity = b.value("intensity", 1.0);
        B.T_emit = b.value("T", 9000.0); B.p_g = b.value("p_g", 4.0); B.decay = b.value("decay", 0.05);
        B.steady = b.value("steady", 0.0);
        if (b.contains("pulses")) for (const auto& p : b["pulses"]) B.pulses.push_back({p[0].get<double>(), p[1].get<double>()});
    }

    Tracer TR;
    TR.S = &S; TR.D = &D; TR.bb = &bb;
    TR.rp = horizon_radius(g_a);
    TR.rcap = photon_orbit_prograde(g_a);

    const int W = S.W, H = S.H;
    const int X0 = S.crop[0], Y0 = S.crop[1], X1 = S.crop[2], Y1 = S.crop[3];
    const int CW = X1 - X0, CH = Y1 - Y0;
    const double pix_angle = S.projection == "rect" ? 2 * std::tan(0.5 * S.hfov) / W : 2 * M_PI / W;

    std::vector<RGB> L_disk(size_t(CW) * CH), L_haze(size_t(CW) * CH), L_sky(size_t(CW) * CH), L_star(size_t(CW) * CH);
    std::vector<float> L_A(size_t(CW) * CH, 0.f), L_hole(size_t(CW) * CH, 0.f);
    std::vector<RGB> L_beacon(size_t(CW) * CH);

    // ---------------- pass A: corner grid (geometry only), per star time sample
    const int GW = CW + 1, GH = CH + 1;
    std::vector<unsigned char> needs_ss(size_t(CW) * CH, 0);
    std::vector<RGB> skyA(size_t(CW) * CH);
    std::vector<float> escA(size_t(CW) * CH, 0.f);
    std::vector<double> fpA(size_t(CW) * CH, pix_angle);
    int NT = S.star_times;
    if (NT <= 0) {
        // automatic: enough shutter samples that a star moves < ~1.5 px between them
        double ang = std::acos(std::clamp(S.cam0.fwd.dot(S.cam1.fwd), -1.0, 1.0));
        double roll = std::acos(std::clamp(S.cam0.up.dot(S.cam1.up), -1.0, 1.0));
        double mv = (ang + roll * 0.5) / pix_angle;
        NT = std::clamp(int(std::ceil(mv / 1.5)), 1, 6);
    }
    for (int ti = 0; ti < NT; ++ti) {
        double u = NT == 1 ? 0.5 : (ti + 0.5) / NT;
        CamPose cp = pose_at(S, u);
        Tetrad T = make_tetrad(cp);
        struct GridRay { Vec3 d; double g; unsigned char esc, touched, hazed; double rmin; };
        std::vector<GridRay> grid(size_t(GW) * GH);
#pragma omp parallel for schedule(dynamic, 4)
        for (int j = 0; j < GH; ++j)
            for (int i = 0; i < GW; ++i) {
                Photon ph; double kt;
                launch(S, T, cp, local_dir(S, X0 + i, Y0 + j), ph, kt);
                TraceResult R;
                TR.trace(ph, kt, false, S.time, pix_angle, nullptr, R);
                GridRay& G = grid[size_t(j) * GW + i];
                G.esc = R.escaped; G.touched = R.touched; G.hazed = R.hazed; G.rmin = R.rmin;
                G.d = R.escaped ? (S.sky_rot * R.dir) : Vec3(0, 0, 1);
                G.g = R.g_inf;
            }
#pragma omp parallel for schedule(dynamic, 4)
        for (int j = 0; j < CH; ++j)
            for (int i = 0; i < CW; ++i) {
                const GridRay* c[4] = {&grid[size_t(j) * GW + i], &grid[size_t(j) * GW + i + 1],
                                       &grid[size_t(j + 1) * GW + i], &grid[size_t(j + 1) * GW + i + 1]};
                size_t pi = size_t(j) * CW + i;
                int nesc = c[0]->esc + c[1]->esc + c[2]->esc + c[3]->esc;
                bool touched = c[0]->touched || c[1]->touched || c[2]->touched || c[3]->touched;
                double rmin = std::min(std::min(c[0]->rmin, c[1]->rmin), std::min(c[2]->rmin, c[3]->rmin));
                bool hazed = c[0]->hazed || c[1]->hazed || c[2]->hazed || c[3]->hazed;
                if (touched || nesc < 4 || rmin < 3.2 * TR.rcap) needs_ss[pi] = 2;
                else if (hazed && needs_ss[pi] == 0) needs_ss[pi] = 1;
                if (nesc == 0) continue;
                // footprint on the celestial sphere (galactic frame)
                Vec3 dc(0, 0, 0);
                double gsum = 0;
                for (auto* q : c) if (q->esc) { dc = dc + q->d; gsum += q->g; }
                dc = dc.norm();
                double gmean = gsum / nesc;
                Vec3 e1, e2;
                tangent_basis(dc, e1, e2);
                auto proj = [&](const GridRay* q, double& pu, double& pv) {
                    double dd = std::max(q->d.dot(dc), 1e-3);
                    pu = q->d.dot(e1) / dd; pv = q->d.dot(e2) / dd;
                };
                double s11, s12, s22;
                double sig = S.pixel_sigma;
                if (nesc == 4) {
                    double p[4][2];
                    for (int q = 0; q < 4; ++q) proj(c[q], p[q][0], p[q][1]);
                    double jx0 = 0.5 * ((p[1][0] - p[0][0]) + (p[3][0] - p[2][0])), jx1 = 0.5 * ((p[1][1] - p[0][1]) + (p[3][1] - p[2][1]));
                    double jy0 = 0.5 * ((p[2][0] - p[0][0]) + (p[3][0] - p[1][0])), jy1 = 0.5 * ((p[2][1] - p[0][1]) + (p[3][1] - p[1][1]));
                    s11 = sig * sig * (jx0 * jx0 + jy0 * jy0);
                    s12 = sig * sig * (jx0 * jx1 + jy0 * jy1);
                    s22 = sig * sig * (jx1 * jx1 + jy1 * jy1);
                } else {
                    // partially captured: isotropic guess from the spread of the escaped corners
                    double spread = 0;
                    for (auto* q : c) if (q->esc) spread = std::max(spread, (q->d - dc).len());
                    spread = std::max(spread, pix_angle);
                    s11 = s22 = sig * sig * spread * spread; s12 = 0;
                }
                double floor2 = 0.02 * pix_angle * pix_angle;  // tiny floor keeps it well conditioned
                s11 += floor2; s22 += floor2;
                double fp = std::sqrt(std::max(s11 + s22, 1e-30));
                fpA[pi] = fp;
                float frac = float(nesc) / 4.f;
                // Doppler / gravitational shift of the sky: intensity ~ g^4 (bolometric), artistic strength
                float gb = float(std::pow(gmean, 4.0 * S.sky_doppler));
                RGB st = stars.eval(dc, e1, e2, s11, s12, s22, S.star_max_radius) * (frac * gb);
                RGB sk = sky.sample(dc, 2.0 * fp) * (frac * gb);
                L_star[pi] += st * (1.f / NT);
                skyA[pi] += sk * (1.f / NT);
                escA[pi] += frac / NT;
            }
    }

    // ---------------- pass B: supersampling where gas or the horizon is involved
    std::atomic<long> nss{0};
    CamPose poseC = pose_at(S, 0.5);
    std::vector<Tetrad> tets;  // pre-built tetrads over the shutter
    std::vector<CamPose> poses;
    const int NTS = 16;
    for (int i = 0; i < NTS; ++i) { poses.push_back(pose_at(S, (i + 0.5) / NTS)); tets.push_back(make_tetrad(poses.back())); }
    (void)poseC;
#pragma omp parallel for schedule(dynamic, 1)
    for (int j = 0; j < CH; ++j) {
        for (int i = 0; i < CW; ++i) {
            size_t pi = size_t(j) * CW + i;
            if (!needs_ss[pi] || !S.disk_on) {
                // sky only: transmittance 1 (or partially captured)
                L_sky[pi] = skyA[pi];
                L_A[pi] = 1.f - escA[pi];
                L_hole[pi] = 1.f - escA[pi];
                continue;
            }
            Rng rng(uint64_t(S.seed) * 0x9E3779B97F4A7C15ULL + uint64_t(Y0 + j) * 100003ULL + uint64_t(X0 + i));
            int N = needs_ss[pi] == 2 ? S.spp : S.spp_haze;
            RGB sd, sh, ss, sb;
            float sT = 0, shole = 0;
            int sq = std::max(1, int(std::sqrt(double(N))));
            double lsum = 0, l2sum = 0;
            int k = 0;
            for (; k < N; ++k) {
                if (k >= S.spp_min && k >= 4 && (k & 3) == 0) {
                    // adaptive: stop when the standard error of the mean luminance is small
                    double m = lsum / k, var = std::max(0.0, l2sum / k - m * m);
                    double se = std::sqrt(var / k);
                    if (se < S.var_thresh * (m + 0.05)) break;
                }
                // stratified sub-pixel position and shutter time
                int sx = k % sq, sy = (k / sq) % sq;
                double jx = (sx + rng.uni()) / sq, jy = (sy + rng.uni()) / sq;
                double tu = (k + rng.uni()) / N;
                int ti = std::min(NTS - 1, int(tu * NTS));
                // Gaussian-ish pixel filter: tent via jitter spread
                double px = X0 + i + 0.5 + (jx - 0.5) * 1.5, py = Y0 + j + 0.5 + (jy - 0.5) * 1.5;
                Photon ph; double kt;
                launch(S, tets[ti], poses[ti], local_dir(S, px, py), ph, kt);
                TraceResult R;
                double tm = S.time + (tu - 0.5) * S.shutter_dt;
                TR.trace(ph, kt, true, tm, pix_angle, &rng, R);
                sd += R.disk; sh += R.haze; sb += R.beacon;
                RGB skyc;
                if (R.escaped) {
                    Vec3 g = S.sky_rot * R.dir;
                    float gb = float(std::pow(R.g_inf, 4.0 * S.sky_doppler));
                    skyc = sky.sample(g, 2.0 * fpA[pi]) * (R.T * gb);
                    ss += skyc;
                    sT += R.T;
                } else {
                    shole += 1.f;
                }
                double lum = (R.disk + R.haze + skyc).lum();
                lum = lum / (1.0 + lum);  // compress so a few hot samples don't dominate the test
                lsum += lum; l2sum += lum * lum;
            }
            N = k;
            nss += N;
            float inv = 1.f / N;
            L_disk[pi] = sd * inv;
            L_beacon[pi] = sb * inv;
            L_haze[pi] = sh * inv;
            L_sky[pi] = ss * inv;
            float Tinf = sT * inv;
            L_A[pi] = 1.f - Tinf;
            L_hole[pi] = shole * inv;
            // stars came from pass A assuming a clear line of sight; attenuate by gas and horizon
            float escf = std::max(escA[pi], 1e-3f);
            L_star[pi] *= std::min(1.f, Tinf / escf);
        }
    }
    double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

    // ---------------- write EXR (channels sorted by name)
    struct Ch { std::string name; std::vector<float> data; };
    std::vector<Ch> chs;
    auto add_rgb = [&](const std::string& n, const std::vector<RGB>& v) {
        Ch r{n + ".R", {}}, g{n + ".G", {}}, b{n + ".B", {}};
        r.data.resize(v.size()); g.data.resize(v.size()); b.data.resize(v.size());
        for (size_t i = 0; i < v.size(); ++i) { r.data[i] = v[i].r; g.data[i] = v[i].g; b.data[i] = v[i].b; }
        chs.push_back(std::move(b)); chs.push_back(std::move(g)); chs.push_back(std::move(r));
    };
    add_rgb("disk", L_disk); add_rgb("haze", L_haze); add_rgb("sky", L_sky); add_rgb("stars", L_star);
    if (S.beacon.on) add_rgb("beacon", L_beacon);
    chs.push_back({"A", L_A});
    chs.push_back({"hole", L_hole});
    if (J.value("output", std::string("layers")) == "beauty") {
        // single RGBA beauty (e.g. an environment probe for Blender): disk + haze + sky + stars
        chs.clear();
        std::vector<float> R(L_disk.size()), G(L_disk.size()), B(L_disk.size()), Al(L_disk.size(), 1.f);
        for (size_t i = 0; i < L_disk.size(); ++i) {
            RGB c = L_disk[i] + L_haze[i] + L_sky[i] + L_star[i];
            R[i] = c.r; G[i] = c.g; B[i] = c.b;
        }
        chs.push_back({"A", Al}); chs.push_back({"B", B}); chs.push_back({"G", G}); chs.push_back({"R", R});
    }
    std::sort(chs.begin(), chs.end(), [](const Ch& x, const Ch& y) { return x.name < y.name; });

    EXRHeader header; InitEXRHeader(&header);
    EXRImage image; InitEXRImage(&image);
    image.num_channels = int(chs.size());
    std::vector<float*> ptrs;
    for (auto& c : chs) ptrs.push_back(c.data.data());
    image.images = reinterpret_cast<unsigned char**>(ptrs.data());
    image.width = CW; image.height = CH;
    header.num_channels = int(chs.size());
    std::vector<EXRChannelInfo> ci(chs.size());
    for (size_t i = 0; i < chs.size(); ++i) {
        std::snprintf(ci[i].name, sizeof(ci[i].name), "%s", chs[i].name.c_str());
    }
    header.channels = ci.data();
    std::vector<int> pt(chs.size(), TINYEXR_PIXELTYPE_FLOAT), rpt(chs.size(), TINYEXR_PIXELTYPE_HALF);
    header.pixel_types = pt.data();
    header.requested_pixel_types = rpt.data();
    header.compression_type = TINYEXR_COMPRESSIONTYPE_ZIP;
    const char* err = nullptr;
    if (SaveEXRImageToFile(&image, &header, S.out.c_str(), &err) != TINYEXR_SUCCESS) {
        std::fprintf(stderr, "EXR write failed: %s\n", err ? err : "?");
        if (err) FreeEXRErrorMessage(err);
        return 2;
    }
    long npx = long(CW) * CH;
    std::fprintf(stderr, "stats: rays %ld  steps/ray %.1f  evals/ray %.1f\n", long(g_rays), double(g_steps) / std::max(1L, long(g_rays)),
                 double(g_evals) / std::max(1L, long(g_rays)));
    std::fprintf(stderr, "tracer: %dx%d  %.2fs  (%ld supersampled rays, %.1f%% px supersampled)  -> %s\n", CW, CH, secs,
                 long(nss), 100.0 * std::count(needs_ss.begin(), needs_ss.end(), 2) / std::max(npx, 1L), S.out.c_str());
    return 0;
}
