// Blackbody colour: Planck spectrum integrated against the CIE 1931 2-degree colour matching
// functions (multi-lobe Gaussian fit of Wyman, Sloan & Shirley, JCGT 2013), converted to linear
// Rec.709 / sRGB primaries and normalised to luminance Y = 1. A LUT in log T keeps it cheap.
#pragma once
#include <cmath>
#include <vector>
#include <algorithm>

struct RGB {
    float r = 0, g = 0, b = 0;
    RGB() = default;
    RGB(float r_, float g_, float b_) : r(r_), g(g_), b(b_) {}
    RGB operator+(const RGB& o) const { return {r + o.r, g + o.g, b + o.b}; }
    RGB operator-(const RGB& o) const { return {r - o.r, g - o.g, b - o.b}; }
    RGB operator*(float s) const { return {r * s, g * s, b * s}; }
    RGB operator*(const RGB& o) const { return {r * o.r, g * o.g, b * o.b}; }
    RGB& operator+=(const RGB& o) { r += o.r; g += o.g; b += o.b; return *this; }
    RGB& operator*=(float s) { r *= s; g *= s; b *= s; return *this; }
    float lum() const { return 0.2126f * r + 0.7152f * g + 0.0722f * b; }
};

inline double cie_lobe(double l, double mu, double s1, double s2) {
    double t = (l - mu) / (l < mu ? s1 : s2);
    return std::exp(-0.5 * t * t);
}
inline void cie_xyz(double l, double& X, double& Y, double& Z) {
    X = 1.056 * cie_lobe(l, 599.8, 37.9, 31.0) + 0.362 * cie_lobe(l, 442.0, 16.0, 26.7) -
        0.065 * cie_lobe(l, 501.1, 20.4, 26.2);
    Y = 0.821 * cie_lobe(l, 568.8, 46.9, 40.5) + 0.286 * cie_lobe(l, 530.9, 16.3, 31.1);
    Z = 1.217 * cie_lobe(l, 437.0, 11.8, 36.0) + 0.681 * cie_lobe(l, 459.0, 26.0, 13.8);
}

inline void blackbody_xyz(double T, double& X, double& Y, double& Z) {
    X = Y = Z = 0;
    const double h = 6.62607015e-34, c = 2.99792458e8, k = 1.380649e-23;
    for (double l = 360.0; l <= 830.0; l += 2.0) {
        double lm = l * 1e-9;
        double B = 1.0 / (std::pow(lm, 5) * (std::exp(h * c / (lm * k * T)) - 1.0));
        double x, y, z;
        cie_xyz(l, x, y, z);
        X += B * x; Y += B * y; Z += B * z;
    }
}

inline RGB xyz_to_rec709(double X, double Y, double Z) {
    return RGB(float(3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z),
               float(-0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z),
               float(0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z));
}

class BlackbodyLUT {
public:
    static constexpr double Tmin = 600.0, Tmax = 80000.0;
    static constexpr int N = 2048;
    std::vector<RGB> lut;
    void build(double white_K) {
        double Xw, Yw, Zw;
        blackbody_xyz(white_K, Xw, Yw, Zw);
        RGB w = xyz_to_rec709(Xw / Yw, 1.0, Zw / Yw);
        lut.resize(N);
        for (int i = 0; i < N; ++i) {
            double T = std::exp(std::log(Tmin) + (std::log(Tmax) - std::log(Tmin)) * i / (N - 1));
            double X, Y, Z;
            blackbody_xyz(T, X, Y, Z);
            RGB c = xyz_to_rec709(X / Y, 1.0, Z / Y);
            // white balance (von Kries-like in RGB), clip out-of-gamut negatives, renormalise to Y=1
            c = RGB(std::max(0.0f, c.r / w.r), std::max(0.0f, c.g / w.g), std::max(0.0f, c.b / w.b));
            float L = c.lum();
            lut[i] = L > 0 ? c * (1.0f / L) : RGB(1, 1, 1);
        }
    }
    RGB operator()(double T) const {
        double u = (std::log(std::clamp(T, Tmin, Tmax)) - std::log(Tmin)) / (std::log(Tmax) - std::log(Tmin)) * (N - 1);
        int i = std::min(int(u), N - 2);
        float f = float(u - i);
        return lut[i] * (1 - f) + lut[i + 1] * f;
    }
};
