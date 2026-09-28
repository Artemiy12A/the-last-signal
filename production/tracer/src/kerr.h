// Kerr spacetime in Cartesian Kerr-Schild coordinates (G = c = M = 1).
//
//   g_{mu nu}  = eta_{mu nu} + f l_mu l_nu
//   g^{mu nu}  = eta^{mu nu} - f l^mu l^nu
//   l_mu = (1, (r x + a y)/(r^2+a^2), (r y - a x)/(r^2+a^2), z/r),  l^mu = (-1, lx, ly, lz)
//   f    = 2 r^3 / (r^4 + a^2 z^2)
//   r    : x^2+y^2 over (r^2+a^2) + z^2 over r^2 = 1
//
// Spin axis is +z, the equatorial plane is z = 0 (world is Z-up, like Blender).
// Photons are traced with the covariant momentum k_mu and the super-Hamiltonian
// H = 1/2 g^{mu nu} k_mu k_nu, so k_t is conserved. The spatial gradient of H is
// obtained with forward-mode automatic differentiation (Dual3).
#pragma once
#include <cmath>
#include <algorithm>

struct Dual3 {
    double v, d0, d1, d2;
};
inline Dual3 dconst(double c) { return {c, 0, 0, 0}; }
inline Dual3 operator+(const Dual3& a, const Dual3& b) { return {a.v + b.v, a.d0 + b.d0, a.d1 + b.d1, a.d2 + b.d2}; }
inline Dual3 operator-(const Dual3& a, const Dual3& b) { return {a.v - b.v, a.d0 - b.d0, a.d1 - b.d1, a.d2 - b.d2}; }
inline Dual3 operator*(const Dual3& a, const Dual3& b) {
    return {a.v * b.v, a.d0 * b.v + a.v * b.d0, a.d1 * b.v + a.v * b.d1, a.d2 * b.v + a.v * b.d2};
}
inline Dual3 operator/(const Dual3& a, const Dual3& b) {
    double iv = 1.0 / b.v, q = a.v * iv;
    return {q, (a.d0 - q * b.d0) * iv, (a.d1 - q * b.d1) * iv, (a.d2 - q * b.d2) * iv};
}
inline Dual3 operator+(const Dual3& a, double c) { return {a.v + c, a.d0, a.d1, a.d2}; }
inline Dual3 operator+(double c, const Dual3& a) { return {a.v + c, a.d0, a.d1, a.d2}; }
inline Dual3 operator-(const Dual3& a, double c) { return {a.v - c, a.d0, a.d1, a.d2}; }
inline Dual3 operator-(double c, const Dual3& a) { return {c - a.v, -a.d0, -a.d1, -a.d2}; }
inline Dual3 operator*(const Dual3& a, double c) { return {a.v * c, a.d0 * c, a.d1 * c, a.d2 * c}; }
inline Dual3 operator*(double c, const Dual3& a) { return {a.v * c, a.d0 * c, a.d1 * c, a.d2 * c}; }
inline Dual3 dsqrt(const Dual3& a) {
    double s = std::sqrt(a.v), h = 0.5 / s;
    return {s, a.d0 * h, a.d1 * h, a.d2 * h};
}
inline double dsqrt(double a) { return std::sqrt(a); }

template <class T>
struct KSGeom {
    T r, f, lx, ly, lz;
};

// Boyer-Lindquist-like radius and the Kerr-Schild null vector at (x, y, z).
template <class T>
inline KSGeom<T> ks_geom(const T& x, const T& y, const T& z, double a) {
    T rho2 = x * x + y * y + z * z;
    T b = rho2 - a * a;
    T r2 = 0.5 * (b + dsqrt(b * b + (4.0 * a * a) * (z * z)));
    T r = dsqrt(r2);
    T den = r2 + a * a;
    KSGeom<T> g;
    g.r = r;
    g.f = (2.0 * r2 * r) / (r2 * r2 + (a * a) * (z * z));
    g.lx = (r * x + a * y) / den;
    g.ly = (r * y - a * x) / den;
    g.lz = z / r;
    return g;
}

inline double ks_radius(double x, double y, double z, double a) {
    double b = x * x + y * y + z * z - a * a;
    return std::sqrt(0.5 * (b + std::sqrt(b * b + 4.0 * a * a * z * z)));
}

inline double horizon_radius(double a) { return 1.0 + std::sqrt(std::max(0.0, 1.0 - a * a)); }

// Radius of the innermost (prograde, equatorial) circular photon orbit. A back-traced photon
// inside it that is still falling can never turn around: it is captured.
inline double photon_orbit_prograde(double a) {
    return 2.0 * (1.0 + std::cos(2.0 / 3.0 * std::acos(-a)));
}
inline double photon_orbit_retrograde(double a) {
    return 2.0 * (1.0 + std::cos(2.0 / 3.0 * std::acos(a)));
}

// Prograde ISCO (Bardeen, Press & Teukolsky 1972), M = 1.
inline double isco_radius(double a) {
    double z1 = 1.0 + std::cbrt(1.0 - a * a) * (std::cbrt(1.0 + a) + std::cbrt(1.0 - a));
    double z2 = std::sqrt(3.0 * a * a + z1 * z1);
    return 3.0 + z2 - std::sqrt((3.0 - z1) * (3.0 + z1 + 2.0 * z2));
}

// Covariant metric at a point: g[4][4] (index 0 = t).
inline void ks_metric(double x, double y, double z, double a, double g[4][4]) {
    KSGeom<double> k = ks_geom(x, y, z, a);
    double l[4] = {1.0, k.lx, k.ly, k.lz};
    for (int m = 0; m < 4; ++m)
        for (int n = 0; n < 4; ++n) g[m][n] = (m == n ? (m == 0 ? -1.0 : 1.0) : 0.0) + k.f * l[m] * l[n];
}

inline double mdot(const double g[4][4], const double* A, const double* B) {
    double s = 0;
    for (int m = 0; m < 4; ++m)
        for (int n = 0; n < 4; ++n) s += g[m][n] * A[m] * B[n];
    return s;
}

// Photon state: position x^i, covariant spatial momentum k_i, coordinate time t.
struct Photon {
    double x[3];
    double k[3];
    double t;
};

struct PhotonDeriv {
    double dx[3];
    double dk[3];
    double dt;
};

// Hamilton's equations. kt = k_t (conserved).
inline void photon_rhs(const Photon& s, double kt, double a, PhotonDeriv& d) {
    Dual3 X{s.x[0], 1, 0, 0}, Y{s.x[1], 0, 1, 0}, Z{s.x[2], 0, 0, 1};
    KSGeom<Dual3> g = ks_geom(X, Y, Z, a);
    Dual3 L = (g.lx * s.k[0] + g.ly * s.k[1]) + (g.lz * s.k[2] - kt);
    Dual3 Q = g.f * L * L;
    double fL = g.f.v * L.v;
    d.dx[0] = s.k[0] - fL * g.lx.v;
    d.dx[1] = s.k[1] - fL * g.ly.v;
    d.dx[2] = s.k[2] - fL * g.lz.v;
    d.dt = -kt + fL;
    d.dk[0] = 0.5 * Q.d0;
    d.dk[1] = 0.5 * Q.d1;
    d.dk[2] = 0.5 * Q.d2;
}

// Contravariant 4-momentum k^mu from covariant (kt, k_i) at a point.
inline void raise_k(const double* x, double kt, const double* k, double a, double out[4]) {
    KSGeom<double> g = ks_geom(x[0], x[1], x[2], a);
    double L = g.lx * k[0] + g.ly * k[1] + g.lz * k[2] - kt;
    double fL = g.f * L;
    out[0] = -kt + fL;
    out[1] = k[0] - fL * g.lx;
    out[2] = k[1] - fL * g.ly;
    out[3] = k[2] - fL * g.lz;
}

// Affine step size bounding the *spatial displacement* of one step to a fraction of the distance
// to the horizon (near) or of r (far). Back-traced photons that fall towards the horizon spin up
// to huge coordinate speeds in ingoing Kerr-Schild coordinates, so a step bounded only in affine
// parameter would catapult them.
inline double step_size(double r, double rp, double speed, double hfac, double far_boost_r) {
    double d = std::max(r - rp, 1e-4);
    double boost = 1.0 + r / far_boost_r;  // weak field far away: larger steps are safe
    double h = hfac * d * std::min(boost, 4.0) / std::max(speed, 1e-12);
    return h;
}

// Classic RK4 step of size h (affine parameter).
inline void rk4_step(Photon& s, double kt, double a, double h, PhotonDeriv& d0out) {
    PhotonDeriv k1, k2, k3, k4;
    Photon tmp;
    photon_rhs(s, kt, a, k1);
    d0out = k1;
    auto add = [&](const Photon& b, const PhotonDeriv& d, double c) {
        Photon o;
        for (int i = 0; i < 3; ++i) {
            o.x[i] = b.x[i] + c * d.dx[i];
            o.k[i] = b.k[i] + c * d.dk[i];
        }
        o.t = b.t + c * d.dt;
        return o;
    };
    tmp = add(s, k1, 0.5 * h);
    photon_rhs(tmp, kt, a, k2);
    tmp = add(s, k2, 0.5 * h);
    photon_rhs(tmp, kt, a, k3);
    tmp = add(s, k3, h);
    photon_rhs(tmp, kt, a, k4);
    const double h6 = h / 6.0;
    for (int i = 0; i < 3; ++i) {
        s.x[i] += h6 * (k1.dx[i] + 2 * k2.dx[i] + 2 * k3.dx[i] + k4.dx[i]);
        s.k[i] += h6 * (k1.dk[i] + 2 * k2.dk[i] + 2 * k3.dk[i] + k4.dk[i]);
    }
    s.t += h6 * (k1.dt + 2 * k2.dt + 2 * k3.dt + k4.dt);
}

// Keplerian (prograde, equatorial) angular velocity; valid off-plane as a cylinder rotation law.
inline double kepler_omega(double r, double a) { return 1.0 / (std::pow(r, 1.5) + a); }

// 4-velocity of gas rotating rigidly-at-this-radius with angular velocity Omega about z, plus an
// optional coordinate radial inflow speed vr (cylindrical, in KS coordinates). Returns false if the
// requested motion is not timelike.
inline bool gas_velocity(double x, double y, double z, double a, double Omega, double vr, double u[4]) {
    double g[4][4];
    ks_metric(x, y, z, a, g);
    double R = std::sqrt(x * x + y * y) + 1e-12;
    double v[4] = {1.0, -Omega * y + vr * x / R, Omega * x + vr * y / R, 0.0};
    double n = -mdot(g, v, v);
    if (n <= 1e-9) {
        // too fast: shrink the spatial velocity until timelike
        for (int it = 0; it < 30 && n <= 1e-9; ++it) {
            v[1] *= 0.9;
            v[2] *= 0.9;
            n = -mdot(g, v, v);
        }
        if (n <= 1e-9) return false;
    }
    double ut = 1.0 / std::sqrt(n);
    for (int m = 0; m < 4; ++m) u[m] = v[m] * ut;
    return true;
}
