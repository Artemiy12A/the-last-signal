// Volumetric accretion disk, plunging streamers and haze around a Kerr black hole.
//
// Emission-absorption in local thermodynamic equilibrium: absorption alpha = kappa * rho,
// source function S = observed colour/intensity of gas at temperature T seen with redshift g.
// Temperature follows the Page-Thorne (relativistic Novikov-Thorne) flux profile, T ~ F^(1/4).
// Gas moves on prograde circular Keplerian orbits outside the ISCO and plunges inside it.
// Turbulence is gradient-noise fBm in log-polar co-rotating coordinates, advected with the
// differential rotation and cross-faded between two "flow layers" so it never over-shears.
#pragma once
#include "color.h"
#include "kerr.h"
#include "noise.h"
#include <vector>
#include <cmath>
#include <algorithm>

struct DiskParams {
    double a = 0.9;
    double r_in = 0;          // 0 -> ISCO
    double r_out = 26.0;      // outer radius where density fades out
    double h_over_r = 0.03;   // midplane scale height H/r
    double flare = 0.15;      // H/r grows as (r/10)^flare
    double T_peak = 7000.0;   // K, local peak temperature
    double kappa = 12.0;      // opacity scale (per M of path at rho = 1)
    double emit_gain = 3.0;   // brightness scale
    double p_T = 4.0;         // intensity ~ (T/T_peak)^p_T   (physical bolometric: 4)
    double p_g = 3.0;         // intensity ~ g^p_g            (physical: 4 bolometric, 3 per nu)
    double color_g = 0.75;    // observed colour temperature = T * g^color_g (physical: 1)
    double time = 0.0;        // disk time, M
    double flow_period = 0.35;// flow-layer lifetime in local orbital periods (per-radius reset)
    double k_ln = 11.0;       // radial noise cells per e-fold of r
    int n_phi = 16;           // azimuthal noise cells per revolution (octave 0)
    double z_cells = 1.2;     // vertical noise cells per scale height
    int octaves = 6;
    double turb = 1.6;        // log-normal turbulence contrast
    double warp = 0.55;       // domain warp strength
    double arms = 0.25;       // m=2 spiral density wave amplitude
    double hot_spots = 1.0;   // compact hot clumps
    double plunge = 0.35;     // plunging-region density relative to the ISCO
    double haze = 0.02;       // haze density (emission only)
    double haze_h = 0.22;     // haze H/r
    double haze_gain = 1.0;
    double inner_soft = 0.25; // width of the inner edge (M)
    double rim = 1.0;         // outer rim raggedness
    double sigma_slope = 0.7; // surface density ~ (r/r_in)^-slope outside the inner edge
    double taper = 0.5;       // outer taper starts at taper * r_out
    double temp_var = 0.18;   // temperature fluctuation amplitude
    double lanes = 0.6;       // dark absorbing lanes (cold gas) strength
    double filaments = 1.4;   // ridged filament strength
    double fil_sharp = 2.5;   // ridge sharpness
    double fil_scale = 1.6;   // filament frequency relative to the base noise
    double floor_dens = 0.25; // diffuse density under the filaments
    double clumps = 0.0;      // large-scale log-normal modulation (clumps, gaps)
    uint32_t seed = 1234;
    // derived
    double r_isco = 6, r_h = 2;
};

class DiskModel {
public:
    DiskParams P;
    const BlackbodyLUT* bb = nullptr;
    std::vector<double> Ttab;  // T(r)/T_peak on a log-r grid
    double lr0 = 0, lr1 = 0;
    int NT = 1024;

    void init(const DiskParams& p, const BlackbodyLUT* lut) {
        P = p;
        bb = lut;
        P.r_isco = isco_radius(P.a);
        if (P.r_in <= 0) P.r_in = P.r_isco;
        P.r_h = horizon_radius(P.a);
        // Page-Thorne flux F(r) (M = Mdot = 1), then T ~ F^1/4, normalised to its peak
        double a = P.a, x0 = std::sqrt(P.r_in);
        double ac = std::acos(a);
        double x1 = 2 * std::cos((ac - M_PI) / 3), x2 = 2 * std::cos((ac + M_PI) / 3), x3 = -2 * std::cos(ac / 3);
        auto F = [&](double r) {
            double x = std::sqrt(r);
            if (x <= x0) return 0.0;
            double t = x - x0 - 1.5 * a * std::log(x / x0)
                       - 3 * (x1 - a) * (x1 - a) / (x1 * (x1 - x2) * (x1 - x3)) * std::log((x - x1) / (x0 - x1))
                       - 3 * (x2 - a) * (x2 - a) / (x2 * (x2 - x1) * (x2 - x3)) * std::log((x - x2) / (x0 - x2))
                       - 3 * (x3 - a) * (x3 - a) / (x3 * (x3 - x1) * (x3 - x2)) * std::log((x - x3) / (x0 - x3));
            return 1.5 / (x * x * x * x * (x * x * x - 3 * x + 2 * a)) * std::max(t, 0.0);
        };
        lr0 = std::log(P.r_in);
        lr1 = std::log(std::max(P.r_out * 4.0, P.r_in * 2));
        Ttab.resize(NT);
        double fmax = 0;
        std::vector<double> ff(NT);
        for (int i = 0; i < NT; ++i) {
            double r = std::exp(lr0 + (lr1 - lr0) * i / (NT - 1));
            ff[i] = F(r);
            fmax = std::max(fmax, ff[i]);
        }
        for (int i = 0; i < NT; ++i) Ttab[i] = std::pow(ff[i] / fmax, 0.25);
    }

    // T(r)/T_peak; inside the ISCO the plunging gas cools quickly
    double temp_profile(double r) const {
        if (r < P.r_in) {
            double s = std::clamp((r - P.r_h) / (P.r_in - P.r_h), 0.0, 1.0);
            double tin = Ttab[std::min(NT - 1, 8)];
            return tin * (0.55 + 0.45 * s);
        }
        double u = (std::log(r) - lr0) / (lr1 - lr0) * (NT - 1);
        if (u >= NT - 1) return Ttab[NT - 1];
        int i = int(u);
        double f = u - i;
        // blend the zero at the ISCO with a warm floor: real disks glow at the edge
        double t = Ttab[i] * (1 - f) + Ttab[i + 1] * f;
        double s = std::clamp((r - P.r_in) / (0.35 * P.r_in), 0.0, 1.0);
        double tfloor = Ttab[std::min(NT - 1, int(0.25 * NT))] * 0.0;  // placeholder hook
        (void)tfloor;
        return std::max(t, 0.62 * (1 - s) + t * s);
    }

    double scale_height(double r) const {
        return P.h_over_r * r * std::pow(std::max(r, 1.0) / 10.0, P.flare);
    }

    // Max |z| where anything can be; used to decide when to march.
    double z_extent(double r) const {
        double Hd = scale_height(std::max(r, P.r_in)) * 4.0;
        double Hh = P.haze > 0 ? P.haze_h * r * 2.6 : 0.0;
        return std::max(Hd, Hh);
    }
    double r_extent() const { return P.r_out * (P.haze > 0 ? 1.8 : 1.25); }
    // is (r, z) inside the dense disk slab (where full noise evaluation happens)?
    bool in_slab(double r, double z) const {
        return r < P.r_out * 1.25 && std::fabs(z) < 4.0 * scale_height(std::max(r, P.r_in));
    }

    double omega(double r) const {
        if (r >= P.r_isco) return kepler_omega(r, P.a);
        // plunging: roughly conserve specific angular momentum of the ISCO orbit
        double wi = kepler_omega(P.r_isco, P.a);
        return wi * std::pow(P.r_isco / std::max(r, P.r_h), 1.6);
    }

    struct Sample {
        float alpha = 0;     // absorption coefficient
        RGB emit_disk;       // alpha * S (emission coefficient) of disk gas
        RGB emit_haze;       // emission coefficient of haze
    };

    // Evaluate the medium at KS position (x,y,z), for a photon with covariant momentum (kt, k[3]).
    // footprint: size of the sampling kernel (M) for noise band-limiting.
    void eval(double x, double y, double z, double kt, const double* k, double time, double footprint,
              Sample& out) const {
        out = Sample();
        double r = ks_radius(x, y, z, P.a);
        if (r < P.r_h * 1.02) return;
        double Rext = r_extent();
        if (r > Rext) return;
        double H = scale_height(std::max(r, P.r_in));
        double zeta = z / H;
        bool in_disk = in_slab(r, z);
        double Hh = P.haze_h * r;
        bool in_haze = P.haze > 0 && std::fabs(z) < 2.6 * Hh;
        if (!in_disk && !in_haze) return;

        // --- redshift g for gas at this point
        double Om = omega(r);
        double vr = 0;
        if (r < P.r_isco) {
            double s = (P.r_isco - r) / (P.r_isco - P.r_h);
            vr = -0.6 * std::pow(std::clamp(s, 0.0, 1.0), 1.5);
        }
        double u[4];
        if (!gas_velocity(x, y, z, P.a, Om, vr, u)) return;
        double kdotu = kt * u[0] + k[0] * u[1] + k[1] * u[2] + k[2] * u[3];
        double g = 1.0 / std::max(kdotu, 1e-6);
        g = std::clamp(g, 0.02, 50.0);

        double Tn = temp_profile(r);
        double lr = std::log(r);
        double phi = std::atan2(y, x);
        double arm = 1.0 + P.arms * std::cos(2.0 * (phi - 0.35 * omega(8.0) * time) - 6.5 * lr);

        if (!in_disk) {
            // haze only: smooth, cheap (two octaves, one flow layer)
            double zh = z / Hh;
            double rad = std::exp(-std::pow(r / (0.8 * P.r_out), 2.0)) * std::clamp((r - P.r_h * 1.2) / 2.0, 0.0, 1.0);
            double psi = phi - Om * std::fmod(time, 50.0);
            double py = psi / (2 * M_PI); py -= std::floor(py);
            float n = fbm_py(float(lr * P.k_ln * 0.3), float(py * 4), float(zh), 4, 2, 0.f, P.seed ^ 0xBEEFu);
            double rho_h = P.haze * rad * std::exp(-0.5 * zh * zh) * std::exp(1.2 * n) * arm;
            if (rho_h > 1e-9) {
                double T = P.T_peak * std::max(Tn, 0.3) * 0.9;
                double I = P.haze_gain * std::pow(T / P.T_peak, P.p_T) * std::pow(g, P.p_g);
                out.emit_haze = (*bb)(T * std::pow(g, P.color_g)) * float(rho_h * I);
            }
            return;
        }

        // --- flow layers: noise advected by differential rotation, cross-faded
        // per-radius layer lifetime: a fixed fraction of the local orbital period, so shear never
        // stretches features by more than ~ (d ln Omega / d ln r) * 2 pi * flow_period
        double Tloc = P.flow_period * 2 * M_PI / std::max(Om, 1e-6);
        double lay_t = time / Tloc;
        float dens_turb = 0, temp_turb = 0, hot = 0, lane = 0, fil = 0, big = 0;
        float fz = float(zeta * P.z_cells * 0.5);
        float fp = float(footprint / r * P.k_ln);          // footprint in octave-0 radial cells
        for (int L = 0; L < 2; ++L) {
            double ph = lay_t + 0.5 * L;
            double cyc = std::floor(ph);
            double age = ph - cyc;
            float wgt = float(std::sin(M_PI * age)); wgt *= wgt;
            if (wgt < 1e-3f) continue;
            uint32_t sd = P.seed + uint32_t(int64_t(cyc) * 7 + L * 101) * 2654435761u;
            double tau = age * Tloc;
            double psi = phi - Om * tau;
            double py = psi / (2 * M_PI);
            py -= std::floor(py);
            float fy = float(py * P.n_phi);
            float fx = float(lr * P.k_ln);
            float w1 = fbm_py(fx * 0.5f + 3.1f, fy * 0.5f, fz * 0.5f, P.n_phi / 2, 1, fp * 0.5f, sd ^ 0xA5A5u);
            float w2 = fbm_py(fx * 0.5f + 8.7f, fy * 0.5f, fz * 0.5f + 4.2f, P.n_phi / 2, 1, fp * 0.5f, sd ^ 0x5A5Au);
            float wx = fx + float(P.warp) * 2.f * w1, wy = fy + float(P.warp) * 1.f * w2;
            float n = fbm_py(wx, wy, fz, P.n_phi, P.octaves, fp, sd);
            int32_t pf = std::max(1, int32_t(P.n_phi * P.fil_scale + 0.5));  // integer period: no seam
            float ys = float(pf) / float(P.n_phi);
            float rf = ridged_py(wx * float(P.fil_scale) + 5.3f, wy * ys, fz * 0.7f, pf, std::max(1, P.octaves - 1),
                                 fp * float(P.fil_scale), sd ^ 0xF11Au, float(P.fil_sharp));
            float n2 = fbm_py(wx * 2.f + 17.f, wy * 2.f, fz * 2.f + 5.f, P.n_phi * 2, 2, fp * 2.f, sd ^ 0x1234u);
            float hs = fbm_py(wx * 1.5f + 40.f, wy * 1.5f, fz, (P.n_phi * 3) / 2, 1, fp * 1.5f, sd ^ 0x7777u);
            // lanes: thin ridged features along the flow (cold, absorbing)
            float ln = fbm_py(fx * 2.5f + 91.f, fy * 0.5f, fz, P.n_phi / 2, 2, fp * 2.5f, sd ^ 0x3C3Cu);
            float rid = 1.f - std::fabs(ln) * 4.f;
            dens_turb += wgt * n;
            fil += wgt * rf;
            if (P.clumps > 0)
                big += wgt * fbm_py(fx * 0.25f + 71.f, fy * 0.25f, fz * 0.3f, std::max(1, P.n_phi / 4), 2, fp * 0.25f, sd ^ 0xC1C1u);
            temp_turb += wgt * n2;
            hot += wgt * std::max(0.f, (hs - 0.2f) / 0.25f);
            lane += wgt * std::max(0.f, rid);
        }

        // --- disk
        double inner = std::clamp((r - (P.r_in - P.inner_soft)) / (2 * P.inner_soft), 0.0, 1.0);
        inner = inner * inner * (3 - 2 * inner);
        double rim = P.r_out * (1.0 + 0.15 * P.rim * dens_turb);
        double r0 = P.taper * rim;
        double outer = r < r0 ? 1.0 : std::max(0.0, 1.0 - (r - r0) / (rim - r0));
        outer = outer * outer * (3 - 2 * outer);
        double sigma = inner * outer * arm * std::pow(std::max(r, P.r_in) / P.r_in, -P.sigma_slope);
        double plunge = 0;
        if (r < P.r_in) {
            double s = (P.r_in - r) / (P.r_in - P.r_h);
            double streak = std::max(0.0, dens_turb * 2.4 + 0.15);
            plunge = P.plunge * std::exp(-2.0 * s) * streak * streak;
        }
        double Hloc = H * (1.0 + 0.3 * dens_turb);
        double zl = z / std::max(Hloc, 1e-6);
        double vert = std::exp(-0.5 * zl * zl);
        double lognorm = std::exp(P.turb * dens_turb * 2.0 - 0.5 * P.turb * P.turb * 0.2);
        double structure = P.floor_dens + P.filaments * double(fil) * double(fil) * 4.0;
        double clump = P.clumps > 0 ? std::exp(P.clumps * 2.0 * double(big) - 0.5 * P.clumps * P.clumps * 0.3) : 1.0;
        double rho = (sigma * lognorm * structure * clump + plunge) * vert;
        if (rho > 1e-7) {
            double T = P.T_peak * Tn * (1.0 + P.temp_var * 2.0 * temp_turb + 0.2 * P.hot_spots * hot);
            // lanes: cold gas absorbs more and glows less
            double cold = P.lanes * lane;
            T *= (1.0 - 0.35 * cold);
            double Tobs = T * std::pow(g, P.color_g);
            double I = P.emit_gain * std::pow(std::max(T, 1.0) / P.T_peak, P.p_T) * std::pow(g, P.p_g) *
                       (1.0 + 1.2 * P.hot_spots * hot);
            double alpha = P.kappa * rho * (1.0 + 2.0 * cold);
            out.alpha = float(alpha);
            out.emit_disk = (*bb)(Tobs) * float(alpha * I);
        }
        if (in_haze) {
            double zh = z / Hh;
            double rad = std::exp(-std::pow(r / (0.8 * P.r_out), 2.0)) * std::clamp((r - P.r_h * 1.2) / 2.0, 0.0, 1.0);
            double rho_h = P.haze * rad * std::exp(-0.5 * zh * zh) * std::exp(1.2 * dens_turb) * arm;
            if (rho_h > 1e-9) {
                double T = P.T_peak * std::max(Tn, 0.3) * 0.9;
                double I = P.haze_gain * std::pow(T / P.T_peak, P.p_T) * std::pow(g, P.p_g);
                out.emit_haze = (*bb)(T * std::pow(g, P.color_g)) * float(rho_h * I);
            }
        }
    }
};
