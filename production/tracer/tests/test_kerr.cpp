// Sanity tests for the Kerr-Schild photon integrator: shadow edges in the equatorial plane,
// Hamiltonian constraint drift.
#include "../src/kerr.h"
#include <cstdio>

static double solve_kt(const double* x, const double* k, double a) {
    KSGeom<double> g = ks_geom(x[0], x[1], x[2], a);
    double A = g.lx * k[0] + g.ly * k[1] + g.lz * k[2];
    double K2 = k[0] * k[0] + k[1] * k[1] + k[2] * k[2];
    double f = g.f;
    return (f * A + std::sqrt(K2 * (1 + f) - f * A * A)) / (1 + f);
}

static double hamiltonian(const Photon& s, double kt, double a) {
    KSGeom<double> g = ks_geom(s.x[0], s.x[1], s.x[2], a);
    double L = g.lx * s.k[0] + g.ly * s.k[1] + g.lz * s.k[2] - kt;
    return 0.5 * (-kt * kt + s.k[0] * s.k[0] + s.k[1] * s.k[1] + s.k[2] * s.k[2] - g.f * L * L);
}

// returns 1 if captured, 0 if escaped
static double far_boost = 1e9;
static int trace(double b, double a, double hfac, int* steps, double* hdrift) {
    const double D = 2000.0;
    Photon s{{b, -D, 0.0}, {0.0, 1.0, 0.0}, 0.0};
    double kt = solve_kt(s.x, s.k, a);
    double rp = horizon_radius(a);
    double rcap = photon_orbit_prograde(a);
    double rprev = 1e30;
    int n = 0;
    PhotonDeriv d;
    double h0 = hamiltonian(s, kt, a);
    for (; n < 200000; ++n) {
        double r = ks_radius(s.x[0], s.x[1], s.x[2], a);
        if (r < rp * 1.01 || (r < rcap && r < rprev)) { *steps = n; *hdrift = hamiltonian(s, kt, a) - h0; return 1; }
        double rdot = s.x[0] * s.k[0] + s.x[1] * s.k[1] + s.x[2] * s.k[2];
        if (r > D * 1.2 && rdot > 0) { *steps = n; *hdrift = hamiltonian(s, kt, a) - h0; return 0; }
        rprev = r;
        PhotonDeriv dd; photon_rhs(s, kt, a, dd);
        double sp = std::sqrt(dd.dx[0]*dd.dx[0] + dd.dx[1]*dd.dx[1] + dd.dx[2]*dd.dx[2]);
        if (sp > 1e5) { *steps = n; *hdrift = 0; return 1; }
        double h = step_size(r, rp, sp, hfac, far_boost);
        rk4_step(s, kt, a, h, d);
    }
    *steps = n; *hdrift = 0; return -1;
}

int main() {
    for (double a : {0.0, 0.9, 0.99}) {
        for (int side : {+1, -1}) {
            double lo = 1.0, hi = 12.0;  // |b|
            int st = 0; double hd = 0;
            for (int it = 0; it < 40; ++it) {
                double mid = 0.5 * (lo + hi);
                if (trace(side * mid, a, 0.05, &st, &hd) == 1) lo = mid; else hi = mid;
            }
            int st2; double hd2;
            trace(side * (lo + 0.3), a, 0.05, &st2, &hd2);
            printf("a=%.2f side=%+d  critical |b| = %.4f   (steps near-miss ray: %d, H drift %.2e)\n", a, side, lo, st2, hd2);
        }
    }
    // accuracy vs step factor for a near-critical ray (a=0.9, retro side)
    for (double hf : {0.2, 0.1, 0.05, 0.025}) {
        double lo = 1.0, hi = 12.0; int st = 0; double hd = 0;
        for (int it = 0; it < 40; ++it) {
            double mid = 0.5 * (lo + hi);
            if (trace(-mid, 0.9, hf, &st, &hd) == 1) lo = mid; else hi = mid;
        }
        printf("hfac=%.3f  critical b (a=0.9, side -1) = %.5f\n", hf, lo);
    }
    // far-field boost: escape-direction accuracy vs step count
    for (double fb : {1e9, 100.0, 40.0, 20.0}) {
        far_boost = fb;
        int st; double hd;
        // follow a b=8 ray and report its final direction
        const double D = 2000.0; double a = 0.9;
        Photon s{{8.0, -D, 0.0}, {0.0, 1.0, 0.0}, 0.0};
        double kt = solve_kt(s.x, s.k, a); double rp = horizon_radius(a); PhotonDeriv d; int n = 0;
        for (; n < 100000; ++n) {
            double r = ks_radius(s.x[0], s.x[1], s.x[2], a);
            double rdot = s.x[0]*s.k[0] + s.x[1]*s.k[1];
            if (r > 2400 && rdot > 0) break;
            PhotonDeriv dd; photon_rhs(s, kt, a, dd);
            double sp = std::sqrt(dd.dx[0]*dd.dx[0] + dd.dx[1]*dd.dx[1] + dd.dx[2]*dd.dx[2]);
            rk4_step(s, kt, a, step_size(r, rp, sp, 0.1, fb), d);
        }
        photon_rhs(s, kt, a, d);
        printf("far_boost=%g steps=%d  escape angle = %.7f rad\n", fb, n, std::atan2(d.dx[1], d.dx[0]));
        (void)st; (void)hd;
    }
    return 0;
}
