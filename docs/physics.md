# THE LAST SIGNAL: physics reference for the Kerr renderer

This is the reference for `production/tracer`, the C++ CPU Kerr ray tracer. It gives the formulas,
the numbers behind them, and where the film departs from real physics. **When physics and cinema
conflict, cinema wins, but each departure is listed in §12.**

Every number marked *(traced)* was computed for this document with an independent Kerr–Schild
Hamiltonian tracer (scipy DOP853, rtol 1e-9, camera at 1000 M). All other numbers come from the
closed-form expressions given here. Section numbers match the headings.

---

## 0. Conventions

* Geometrized units, G = c = 1. Lengths are in **M** = GM/c^2 and times in GM/c^3. Mass
  scaling: 1 M of time = 4.93 µs × (M/M_sun). For 10^6 M_sun, 1 M = 4.93 s and 1 M of length = 1.48e6 km.
* Signature (−,+,+,+). The spin is along **+z**. For a > 0 the hole and a prograde disk rotate
  counter-clockwise when viewed from +z (increasing φ).
* **Screen orientation.** If the projected spin axis points *up* on screen, the **approaching
  side is on the left**. The shadow's flattened edge is also on the left, and the shadow is shifted
  **right**, toward the receding side. This matches DNGR [1] and Bardeen's α = −ξ/sin i [2].
* Photon constants: E = −p_t, L = p_φ, λ = L/E, and Carter's η = Q/E^2 [4].
* `r_+ = M + sqrt(M²−a²)` is the outer horizon and `r_- = M − sqrt(M²−a²)` the inner one.

---

## 1. Key numbers at a glance

### 1.1 Spin table (M = 1)

| a | r_+ | r_ISCO (pro) | r_ISCO (retro) | r_ph pro | r_ph retro | η_rad = 1−E_ISCO | Ω_ISCO | P_orb(ISCO) | 1/κ (e-fold) |
|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 2.000 | 6.000 | 6.000 | 3.000 | 3.000 | 5.7 % | 0.0680 | 92.3 | 4.00 |
| 0.3 | 1.954 | 4.979 | 6.949 | 2.630 | 3.329 | 6.9 % | 0.0877 | 71.6 | 4.10 |
| 0.5 | 1.866 | 4.233 | 7.555 | 2.347 | 3.532 | 8.2 % | 0.1086 | 57.9 | 4.31 |
| 0.6 | 1.800 | 3.829 | 7.851 | 2.189 | 3.630 | 9.1 % | 0.1236 | 50.8 | 4.50 |
| 0.7 | 1.714 | 3.393 | 8.143 | 2.013 | 3.725 | 10.4 % | 0.1439 | 43.7 | 4.80 |
| **0.8** | **1.600** | **2.907** | 8.432 | **1.811** | **3.819** | **12.2 %** | 0.1737 | **36.2** | **5.33** |
| 0.9 | 1.436 | 2.321 | 8.717 | 1.558 | 3.910 | 15.6 % | 0.2254 | 27.9 | 6.59 |
| 0.99 | 1.141 | 1.454 | 8.972 | 1.168 | 3.991 | 26.4 % | 0.3644 | 17.2 | 16.2 |
| 0.998 | 1.063 | 1.237 | 8.994 | 1.074 | 3.998 | 32.1 % | 0.4213 | 14.9 | 33.6 |

Notes on the columns:
* P_orb = 2π/Ω is measured in coordinate time at infinity.
* κ = (r_+ − r_-)/(2(r_+² + a²)) is the surface gravity. 1/κ is the e-folding time of the redshift
  of an infalling beacon (§9).
* The ergosphere reaches r = 2M at the equator for every spin.

### 1.2 Recommended film configuration (details in §11)

| Parameter | Value | Resulting numbers |
|---|---|---|
| Spin | a = 0.8 | Shadow offset +1.69 M toward the receding side. 9 % flattening "dent" on the approaching side at i = 80°. |
| Reveal inclination | i = 80° (usable range 75–84°) | |
| Disk inner edge | ISCO, 2.91 M | Soft plunging-region glow inside it. |
| Disk outer edge | 30 M, tapered from 18 M | |
| Temperature | Emitted T_peak = 6500 K at r ≈ 4.4 M (Page–Thorne shape) | White balance at 6500 K. Approaching side 8.7–9.0 kK (blue-white). Receding side 2.6–3.2 kK (amber). |
| Beaming | brightness ∝ g^p on a luminance-normalized colour, p = 2 | Physics gives about 150× (bolometric) or 1400× (visual) at the temperature peak. p = 2 gives 12×. |
| Disk thickness | Emissive core H/r ≈ 0.03 (Gaussian), sparse turbulent atmosphere to about 0.1 | |

---

## 2. Spacetime, rays and camera

The renderer author has already validated a Cartesian Kerr–Schild integrator (§10.2). This
section is therefore a compact reference for checking that code.

### 2.1 Cartesian Kerr–Schild (KS) metric

This form is horizon-penetrating and has no polar singularity [27, 28]:

```
g_{μν} = η_{μν} + f l_μ l_ν          g^{μν} = η^{μν} − f l^μ l^ν      η = diag(−1,1,1,1)

R² = x²+y²+z²,   w = R² − a²
r² = ½ ( w + sqrt(w² + 4a²z²) )          # stable form for w<0: r² = 2a²z² / (sqrt(w²+4a²z²) − w)
f  = 2 M r³ / (r⁴ + a² z²)
l_μ = ( 1, (r x + a y)/(r²+a²), (r y − a x)/(r²+a²), z/r )
l^μ = η^{μν} l_ν = (−1, l_x, l_y, l_z)       # l is null for both η and g
```

Relation to Boyer–Lindquist-like spheroidal coordinates. The sign below was verified numerically
against the metric components g_TΦ, g_rΦ, g_Tr and g_rr:

```
x + i y = (r + i a) sinθ e^{iΦ},   z = r cosθ
T = t_BL + ∫ 2Mr/Δ dr,   Φ = φ_BL + ∫ a/Δ dr      (ingoing KS),   Δ = r² − 2Mr + a²
∂x^i/∂r |_(T,θ,Φ) = (sinθ cosΦ, sinθ sinΦ, cosθ) = (l_x, l_y, l_z)   ← handy
equatorial plane: z = 0 and x² + y² = r² + a²
```

The Killing vectors in Cartesian KS are `ξ_t = ∂_T = (1,0,0,0)` and
`ξ_φ = (0, −y, x, 0)`. The invariants `g_tt = g(ξ_t,ξ_t)`, `g_tφ = g(ξ_t,ξ_φ)` and
`g_φφ = g(ξ_φ,ξ_φ)` equal their Boyer–Lindquist values. For example, on the equator
g_tφ = −2Ma/r (verified).

### 2.2 Hamiltonian ray equations

Use `H = ½ g^{μν} k_μ k_ν = ½[ η^{μν}k_μk_ν − f (l·k)² ]` with `l·k ≡ l^μ k_μ = −k_t + l_i k_i`.
H = 0 on a null ray.

```
dx^μ/dλ = η^{μν}k_ν − f (l·k) l^μ                   (so dt/dλ = −k_t + f (l·k))
dk_t/dλ = 0                                          (E = k_t conserved; also k_φ = x k_y − y k_x = −L)
dk_i/dλ = ½ (∂_i f) (l·k)² + f (l·k) (∂_i l_j) k_j   (i, j spatial)

With D = r⁴ + a²z² and s = r² + a²:
∂_i r   = ( x r³/D,  y r³/D,  z r s/D )
∂_i f   = 2Mr² [ (3a²z² − r⁴) ∂_i r − 2a²rz δ_iz ] / D²
∂_i l_x = [ (x ∂_i r + r δ_ix + a δ_iy) s − (r x + a y) 2r ∂_i r ] / s²
∂_i l_y = [ (y ∂_i r + r δ_iy − a δ_ix) s − (r y − a x) 2r ∂_i r ] / s²
∂_i l_z = δ_iz / r − z ∂_i r / r²
```

These derivatives agree with central finite differences of H to about 1e-10. Dual-number autodiff
of H is an equally good alternative. Keep the finite-difference comparison as a unit test.

**Constants of motion (diagnostics).**
* `E = k_t` for the backward ray (§2.4). The photon's angular momentum is
  `L = −(x k_y − y k_x)`, because the backward ray has k_φ = −L.
* The Carter constant uses `k_θ = cotθ (x k_x + y k_y) − r sinθ k_z`:
  `Q = k_θ² + cos²θ (L²/sin²θ − a²E²)` [4].
* Drift in these, and in H/E², measures integration error. The Boyer–Lindquist equations
  `Σ dr/dσ = ±√R(r)` and `Σ dθ/dσ = ±√Θ(θ)` use
  `R = (E(r²+a²) − aL)² − Δ[(L−aE)² + Q]` and `Θ = Q + a²E²cos²θ − L²cot²θ` [2, 5]. They are
  useful for checks and analytic turning points, but the Hamiltonian form is more robust at
  turning points [1].

### 2.3 Observers (camera and emitters) from Killing vectors

These constructions work in any coordinates:

```
static:           u = ξ_t / sqrt(−g_tt)                                  (only outside the ergosphere, r>2M at equator)
ZAMO:             ω = −g_tφ/g_φφ ,   u = N (ξ_t + ω ξ_φ),  N = 1/sqrt(−(g_tt + 2ω g_tφ + ω² g_φφ))
circular orbit:   u = u^t (ξ_t + Ω ξ_φ),  u^t = 1/sqrt(−(g_tt + 2Ω g_tφ + Ω² g_φφ)),  Ω = ±M^½ / (r^{3/2} ± a M^½)
                  equatorial closed form:  u^t = (r^{3/2} + a) / ( r^{3/4} sqrt(r^{3/2} − 3 r^{1/2} + 2a) )     [3]
arbitrary moving camera: any unit timelike u (e.g. the probe's integrated 4-velocity)
```

**Tetrad.** Use Gram–Schmidt with g_{μν}. Start from `u`. Then take the coordinate direction
vectors (0, forward), (0, up) and (0, right), and for each one set `e ← v + (v·u) u`, subtract
the projections onto the earlier e's, and normalize.

### 2.4 Launching camera rays: aberration comes for free

For a pixel with unit sky direction `n = (n_f, n_r, n_u)` in the camera frame, a photon arriving
from direction n has `p = E_cam (u − n^a e_a)`. Trace the **backward ray** `k = −p` forward in λ:

```
k^μ = −u^μ + n^a e_a^μ          (so k·u_cam = +1, i.e. E_cam ≡ 1)
k_μ = g_{μν} k^ν                (integrate covariant k; t decreases along λ)
```

Because u is the camera's own 4-velocity, special-relativistic aberration and the Doppler shift
of the whole sky are included automatically. DNGR instead launches from the FIDO/ZAMO frame and
applies the explicit aberration formula for a camera moving at speed β along e_y [1, eq. A.9]:
`n_Fy = (−N_y + β)/(1 − βN_y)` and `n_F{x,z} = −sqrt(1−β²) N_{x,z}/(1 − βN_y)`. The effect is
large: a camera on a prograde geodesic orbit at 2.6 M around a = 0.999 sees a much smaller shadow
than a ZAMO camera at the same point [1, Fig. 12].

At the cinematic distances used here (≥ 20 M), static and ZAMO cameras look practically identical.
An orbiting camera at 6 M (v ≈ 0.5c) does not look like them.

### 2.5 Photon orbits and the shadow (Bardeen)

**Spherical photon orbits** exist for r_ph,pro ≤ r ≤ r_ph,retro, with
`r_ph,± = 2M[1 + cos(⅔ arccos(∓a/M))]` [2, 7]. For a = 0.8 the range is 1.811–3.819 M. Their
constants are:

```
ξ(r) = λ = [ r²(3M − r) − a²(r + M) ] / [ a (r − M) ]
η(r)     = r³ [ 4 a² M − r (r − 3M)² ] / [ a² (r − M)² ]
```

**Shadow edge for a distant observer at inclination i** (the critical curve, "shadow"; screen
coordinates in M) [2]:

```
α(r) = −ξ(r) / sin i ,     β(r) = ± sqrt( η(r) + a² cos² i − ξ(r)² cot² i )   (keep r where β² ≥ 0)
```

Shadow shape at i = 80° (α_L and α_R are the left and right edges; dent = Hioki–Maeda flattening
relative to a circle through the top, bottom and right edges [32]):

| a | α_L | α_R | half-height | centre offset | dent |
|---|---|---|---|---|---|
| 0.3 | −4.57 | 5.76 | 5.195 | +0.60 | 1.0 % |
| 0.6 | −3.86 | 6.30 | 5.193 | +1.22 | 4.5 % |
| 0.7 | −3.58 | 6.47 | 5.192 | +1.45 | 6.5 % |
| **0.8** | **−3.26** | **6.64** | **5.191** | **+1.69** | **9.3 %** |
| 0.9 | −2.87 | 6.81 | 5.189 | +1.97 | 13.6 % |
| 0.99 | −2.28 | 6.95 | 5.188 | +2.34 | 22.1 % |

* **The size of the shadow barely depends on spin.** Schwarzschild has a circle of radius
  √27 M = 5.196 M. For every spin and inclination the diameter stays within a few percent of
  2√27 M ≈ 10.4 M [20]. Spin mostly **shifts** the shadow and **flattens its approaching side**.
* For a camera at finite distance d, the Schwarzschild shadow angular radius is
  `sin θ_sh = (√27 M/d) sqrt(1 − 2M/d)` [31]. At 50 M this gives 5.9°; at 30 M, 9.6°.
* The DNGR prescription [1, eqs. A.5–A.6, A.13–A.14] classifies (b, q) as horizon-bound or
  escaping without integration. It is useful as an early-out for pixels deep inside the shadow.

---

## 3. The photon ring: what it should look like

Terminology follows [7, 8]:
* The **critical curve** is the shadow edge in §2.5.
* The **n-th subring** is formed by light that made n extra half-orbits (n equatorial crossings
  beyond the direct image).
* The **n = 1** image of an equatorial disk is the broad "lensing ring" (also called the secondary
  image). **n ≥ 2** is the photon ring proper.

**Self-similar nesting.** Successive subrings are demagnified by e^{−γ}, rotated by δ, and
delayed by τ [6, 7]:

```
width_{n+1} / width_n ≈ e^{−γ}     flux_{n+1}/flux_n ≈ e^{−γ}     t_{n+1} − t_n ≈ τ
γ = (4 r √χ) / (a sqrt(−u_−)) · K(u_+/u_−),    χ = 1 − M Δ(r) / (r (r − M)²)
u_± = r/(a²(r−M)²) [ −r³ + 3M²r − 2a²M ± 2 sqrt( MΔ(2r³ − 3Mr² + a²M) ) ]
Schwarzschild:  γ = δ = π,  τ = 3√3 π M ≈ 16.3 M
```

Here r is the photon-shell radius that maps to a given angle around the ring [7, eq. 10], and K is
the complete elliptic integral. Values across the shell, from the prograde end to the retrograde
end, computed here:

| a | γ range | e^{−γ} (width/flux ratio per subring) |
|---|---|---|
| 0 | π | 0.043 (≈ 1/23) |
| 0.6 | 2.95–3.14 | 0.043–0.052 |
| **0.8** | **2.73–3.14** | **0.043–0.065** |
| 0.9 | 2.47–3.14 | 0.043–0.085 |
| 0.99 | 1.87–3.14 | 0.043–0.155 |

What this means on screen:
* **Thin nested lines.** For an a = 0.8 hole viewed at 80°:
  * The n = 1 lensing ring is roughly 0.5–1 M wide. It is centred about 5 % outside the critical
    curve and is about 2–3× brighter than the local direct emission [8].
  * n = 2 is 1/15–1/23 of that width (about 0.03–0.06 M) and fainter by the same factor.
  * n = 3 is another 15–23× thinner.
  * Example framing: the shadow diameter (10.4 M) fills 40 % of a 2048 px frame, i.e. about 80
    px/M. Then n = 1 is 40–80 px, **n = 2 is 2–5 px, and n = 3 is sub-pixel**. The ring looks
    like one bright thin line on top of a softer lensing ring, slightly **wider and brighter on
    the approaching (flattened) side**, where e^{−γ} is largest.
* **Luminosity share.** The n = 1 subring carries about 10 % of total flux in GRMHD models [7].
  For optically thin emission, intensity rises only logarithmically toward the critical curve
  (I ~ n) [7, 8].
* **Time echoes.** Each subring shows the disk as it was τ ≈ 16 M earlier and rotated by δ (≈ π
  for Schwarzschild, so successive images appear on opposite sides). A flare on the disk
  therefore **echoes around the ring** about 16 M later at ~1/20 of the brightness. This is
  automatic if emission is sampled at the ray's coordinate time t(λ). During flux eruptions the
  ring's relative brightness can change by an order of magnitude at high inclination [24].

Numerical requirements:
* Rays near the critical curve wind for a logarithmically long time. Budget at least 50 steps per
  half-orbit (path ~π·3 M), and set a hard cap of about 20 k steps. A ray that hits the cap is
  counted as captured, since it is inside the ring to within the numerical error.
* Anti-alias the ring region with extra samples, or adaptively supersample pixels whose
  neighbours differ in crossing count. Otherwise n = 2 crawls and flickers.

---

## 4. The accretion disk: Novikov–Thorne / Page–Thorne

### 4.1 Circular-orbit kinematics (equatorial, prograde, M = 1) [3]

```
Ω = 1 / (r^{3/2} + a)
E = (r^{3/2} − 2 r^{1/2} + a) / ( r^{3/4} sqrt(r^{3/2} − 3 r^{1/2} + 2a) )
L = (r² − 2a r^{1/2} + a²)    / ( r^{3/4} sqrt(r^{3/2} − 3 r^{1/2} + 2a) )
ISCO (Bardeen–Press–Teukolsky):
  Z1 = 1 + (1−a²)^{1/3} [ (1+a)^{1/3} + (1−a)^{1/3} ],   Z2 = sqrt(3a² + Z1²)
  r_ISCO = 3 + Z2 ∓ sqrt( (3 − Z1)(3 + Z1 + 2 Z2) )     (− prograde, + retrograde)
```

### 4.2 Flux and temperature

The Page–Thorne flux emitted from each face of the disk, in the local rest frame, has this closed
form [9, 10]. It was verified here against direct numerical integration of the defining integral
to about 1e-9.

```
x = sqrt(r/M),  x0 = sqrt(r_ISCO/M),  and x1, x2, x3 are the roots of x³ − 3x + 2a = 0:
  x1 = 2cos(⅓ arccos a − π/3),  x2 = 2cos(⅓ arccos a + π/3),  x3 = −2cos(⅓ arccos a)

F(r) = (3 Ṁ c² / (8π r_g²)) · B(x) / ( r x² (x³ − 3x + 2a) )         (r in M;  r_g = GM/c²)
B(x) = x − x0 − (3/2) a ln(x/x0)
       − 3(x1−a)²/(x1(x1−x2)(x1−x3)) · ln((x−x1)/(x0−x1))
       − 3(x2−a)²/(x2(x2−x1)(x2−x3)) · ln((x−x2)/(x0−x2))
       − 3(x3−a)²/(x3(x3−x1)(x3−x2)) · ln((x−x3)/(x0−x3))
T_eff(r) = (F/σ_SB)^{1/4}
```

* For a = 0, x2 = 0; use a = 1e-7 in code.
* At large r this reduces to the Newtonian `F = 3GMṀ/(8πr³) (1 − sqrt(r_in/r))`.
* F = 0 at the ISCO (zero-torque inner boundary).

**Where the temperature peaks** (local frame; T ∝ F^{1/4}):

| a | r_ISCO | r(T_peak) | r_peak / r_ISCO | T(1.1 r_ISCO)/T_pk | T(20M)/T_pk | T(50M)/T_pk |
|---|---|---|---|---|---|---|
| 0 | 6.00 | 9.55 | 1.59 | 0.69 | 0.77 | 0.44 |
| 0.6 | 3.83 | 5.95 | 1.55 | 0.71 | 0.57 | 0.31 |
| **0.8** | **2.91** | **4.42** | **1.52** | **0.73** | **0.47** | 0.25 |
| 0.9 | 2.32 | 3.44 | 1.48 | 0.75 | 0.39 | 0.21 |
| 0.99 | 1.45 | 1.98 | 1.36 | 0.83 | 0.25 | 0.13 |

For comparison, the Newtonian profile peaks at (49/36) r_in = 1.36 r_in. The full a = 0.8 profile
of T/T_pk is: r = 3.0 → 0.46, 3.2 → 0.73, 3.5 → 0.90, 4.4 → 1.00, 6 → 0.93, 8 → 0.81,
12 → 0.65, 20 → 0.47, 30 → 0.36, 40 → 0.29.

**Practical rendering form.** Tabulate `T(r) = T_pk · (F(r)/F_pk)^{1/4}` from the closed form into
a 1-D LUT (512 samples in log r). A cheaper approximation with the right shape is the Newtonian
profile with r_in → r_ISCO, stretched by 1.52/1.36 in (r − r_ISCO).

**Physical temperatures are far from "white-gold".** At Ṁ = 0.1 Ṁ_Edd, a = 0.6:
* T_pk ≈ 5×10^6 K for 10 M_sun, 2×10^5 K for 4×10^6 M_sun, 9×10^4 K for 10^8 M_sun, and
  5×10^4 K for 10^9 M_sun. T_pk ∝ M^{−1/4} Ṁ^{1/4}.
* Getting 6500 K from a thin accretion disk needs about 4×10^12 M_sun, or Ṁ ≈ 3×10^{−5} Ṁ_Edd
  for 10^9 M_sun. At such low rates real flows become hot, thick and radiatively inefficient
  (ADAF/MAD, §7), not thin disks.
* Interstellar faced the same problem. Its disk was "anemic", not accreting, and had cooled to a
  uniform 4500 K [1]. **Our visible-light temperature scale is an artistic choice (§12).**

### 4.3 Emission inside the ISCO (plunging region)

* In Novikov–Thorne the stress, and therefore F, drops to zero at the ISCO. Gas then plunges on a
  geodesic that keeps E_ISCO and L_ISCO [11].
* In MHD simulations the stress does not vanish there, and the plunging region emits a little. It
  is dim and strongly redshifted, but it fills the gap between the ISCO and the shadow [13]. This
  plunging-region emission has now been reported in X-ray binaries [14].
* Plunging gas also forms spiral inflow streamers in GRMHD (§7).

**Plunging 4-velocity** (equatorial Boyer–Lindquist, then converted to KS; normalization u·u = −1
verified):

```
u^t_BL = [ (r² + a² + 2a²M/r) E − (2aM/r) L ] / Δ
u^φ_BL = [ (1 − 2M/r) L + (2aM/r) E ] / Δ
u^r    = − sqrt( [E(r²+a²) − aL]² − Δ[r² + (L − aE)²] ) / r²
KS:  u^T = u^t_BL + (2Mr/Δ) u^r ,   u^Φ = u^φ_BL + (a/Δ) u^r       (both finite at r_+)
Cartesian:  u^μ = u^T ξ_t + u^Φ ξ_φ + u^r (0, l_x, l_y, l_z)
```

**Film treatment.** Give the plunging region an emissivity of about 3–8 % of the ISCO-adjacent
disk, falling to zero near r_+. Advect it with the plunging velocity above (the pattern speed is
dΦ/dT = u^Φ/u^T). Compute its colour with this velocity's own g. The result is a faint deep-red
veil and inward-spiralling filaments that tie the disk to the photon ring.

### 4.4 Thickness

* Radiatively efficient thin disks have H/r ~ 0.01–0.05.
* Hot, low-Ṁ flows, which are the ones EHT sees, have H/r ~ 0.3–1.
* **For the film, use a thin-but-volumetric disk:**
  * An emissive, optically thick core with a Gaussian vertical profile
    `ρ ∝ exp(−z²/2H²)`, H/r ≈ 0.03. This gives a crisp dark lane where the near side occludes the
    lensed far side.
  * A sparse, optically thin turbulent atmosphere reaching |z| ≈ 0.1 r.
  * At i = 80° the line of sight is 10° above the plane (tan 10° = 0.18). An H/r of 0.03 therefore
    still reads as a thin sheet with visible depth, and its upper surface shows turbulence in
    grazing light.

---

## 5. Frequency shifts and radiative transfer

### 5.1 The g-factor

`g ≡ ν_obs/ν_em = (p·u_obs)/(p·u_em) = (k·u_cam)/(k·u_em)`. The overall sign of k cancels. With
the launch normalization k·u_cam = 1:

```
g = 1 / (k·u_em)
circular emitter:   k·u_em = u^t (k_t + Ω k_φ),  k_φ = x k_y − y k_x
                    ⇒  g = 1 / ( u^t (1 − Ω λ) ) · (E_cam/E_∞)   with λ = L/E of the photon      [11]
plunging emitter:   k·u_em = u^T k_t + u^Φ k_φ + u^r (l_x k_x + l_y k_y + l_z k_z)
static observer at infinity:  g → 1/(u^t(1 − Ωλ)) exactly
```

### 5.2 Invariants

* `I_ν/ν³` is conserved along a ray (Liouville) [34, 35]. **Surface brightness is not changed by
  lensing.** Only solid angle changes, which is how point sources get magnified (§8).
* **An observed blackbody is still a blackbody at the shifted temperature:**
  `I_ν,obs = g³ B_ν(ν/g, T) = B_ν(ν, gT)`. The colour pipeline therefore needs only a 1-D LUT
  mapping T to linear RGB, e.g. Planck × CIE 1931 CMFs [38] → XYZ → working space. The repo already
  has one.
* Bolometric intensity scales as `I = g⁴ I_em`. A power-law emitter with I_ν ∝ ν^{−α} scales as
  g^{3+α}.
* **Volume transfer**, front to back along the backward ray:

```
dℓ_em = (k·u_em) dλ = dλ / g                       # path length in the gas frame
I_ν,obs  += Tr · g³ j_ν,em(ν/g) · dℓ_em             # j_ν,em = emissivity in gas frame
Tr       *= exp( −α_ν,em(ν/g) · dℓ_em )             # absorption in gas frame
thermal gas: j_ν = α_ν B_ν(T)  ⇒ contribution = Tr·(1−e^{−Δτ})·B_ν(ν, gT)
```

* **Thin disk surface.** At a plane crossing, add `Tr · ε · B_ν(ν, g T(r))` and multiply Tr by
  (1 − opacity). DNGR attenuated by optical thickness and let the beam continue to later images
  [1, A.4].

### 5.3 Sky and camera

* A static camera at radius r_c sees the whole sky blueshifted by `1/sqrt(−g_tt)`. That is 3.5 %
  at 30 M and 1 % at 100 M; keep it or ignore it.
* A moving camera also Doppler-shifts and beams the sky ahead of it. This is physical but usually
  distracting; see §12.

---

## 6. Doppler beaming: how strong is it?

The table below gives the extreme g-values on a single ring of the **direct (n = 0) disk image**,
including light bending and gravitational redshift *(traced)*. The camera is far away. "App" is
the approaching side (max g) and "rec" is the receding side (min g).

| a | i | r | g_app | g_rec | g ratio | bolometric ratio (g⁴) | I_ν ratio at fixed colour (g³) |
|---|---|---|---|---|---|---|---|
| 0 | 80° | 6 | 1.387 | 0.475 | 2.92 | 73 | 25 |
| 0.6 | 80° | 6 | 1.349 | 0.492 | 2.74 | 57 | 21 |
| 0.7 | 80° | 6 | 1.344 | 0.494 | 2.72 | 55 | 20 |
| 0.8 | 80° | 6 | 1.339 | 0.496 | 2.70 | 53 | 20 |
| 0.9 | 80° | 6 | 1.334 | 0.498 | 2.68 | 52 | 19 |
| 0.7 | 75° | 6 | 1.320 | 0.498 | 2.65 | 49 | 19 |
| 0.7 | 85° | 6 | 1.331 | 0.491 | 2.71 | 54 | 20 |
| **0.8** | 80° | **3.2** (≈1.1 ISCO) | 1.446 | 0.278 | 5.19 | 727 | 140 |
| **0.8** | 80° | **4.4** (T peak) | 1.390 | 0.395 | 3.52 | 154 | 44 |
| 0.8 | 80° | 12 | 1.250 | 0.666 | 1.88 | 12 | 7 |
| 0.8 | 80° | 25 | 1.180 | 0.780 | 1.51 | 5 | 3 |
| 0.8 | 75° | 4.4 | 1.351 | 0.401 | 3.37 | 129 | 38 |
| 0.8 | 60° | 4.4 | 1.205 | 0.425 | 2.84 | 65 | 23 |
| 0.8 | 30° | 4.4 | 0.879 | 0.505 | 1.74 | 9 | 5 |

* **At r = 6 M and i = 80°, the approaching side is about 2.7× bluer in frequency and about 55×
  brighter bolometrically**, almost independent of spin.
* Near the ISCO of an a = 0.8 hole the bolometric contrast exceeds 700×.
* DNGR quoted shift factors of "order 1.5 and 0.4" for its disk [1]. Our 1.34–1.45 and 0.28–0.50
  agree.
* At low inclination (30°) both sides are redshifted. Transverse Doppler plus gravity dominate,
  and the asymmetry is mild.

**What the eye would see is even more extreme**, because the receding side slides down the Wien
tail. With T_em = 6500 K at r = 4.4 M (a = 0.8, i = 80°):
* The approaching side is observed at T = 9.0 kK (blue-white) and the receding side at 2.6 kK
  (amber-red).
* The ratio of visual luminance (photopic V(λ) weighting) is **about 1400×**. At r = 6 M it is
  about 160×.
* A fully physical frame is therefore a bright blue-white crescent on one side and near-black on
  the other, as in DNGR Fig. 15c [1]. Nolan and Franklin rejected it as confusing.

**Tempering it (recommended controls):**
1. **Keep colour and brightness separate.**
   * Colour: compute the observed chromaticity from B(ν, g_c T) with g_c = g^q. Use q = 1
     (physical) or q ≈ 0.8 for a gentler hue swing.
   * Brightness: remove the luminance of that shifted blackbody, DNGR style
     `{R,G,B}/(0.30R+0.59G+0.11B)` [1, A.6]. Then multiply by the intrinsic luminance × **g^p**.
2. **Recommended p = 2.** This gives 7× at 6 M and 12× at the temperature peak, versus 55× and
   150× physical: clearly lopsided, and the receding side still reads. p = 1.5 gives 4.4× and 6.6×.
   Use p = 3 for a "this is what physics says" beat.
3. Add a soft ceiling on the contrast between the two sides, e.g.
   `B_final = B · min(g^p, g_max^p) / (1 + (g^p/c)^s)`, or apply a shoulder in log space before
   the ACES tone map. This keeps the approaching limb from clipping.

---

## 7. What real black holes and GRMHD simulations look like

**EHT observations**
* **M87\*:**
  * The ring diameter is **42 ± 3 µas**, with a central brightness depression of more than 10:1
    and M = 6.5 × 10^9 M_sun [15, 17].
  * The angular gravitational radius is θ_g = GM/Dc² = 3.8 ± 0.4 µas, so the ring is about
    11 θ_g across. The critical curve is 2√27 ≈ 10.4 θ_g, and the observed emission ring lies just
    outside it.
  * The ring is **brighter in the south**. This is Doppler beaming from gas and field rotating
    clockwise on the sky. If the spin is aligned with the jet, the spin vector points away from
    Earth [16].
  * The viewing inclination is only ~17°, so the brightness asymmetry is a factor of a few, not
    the hundreds seen for a thin disk at 80° (§6).
* **Sgr A\*:**
  * The image is a **thick ring 51.8 ± 2.3 µas across** with modest azimuthal asymmetry, a
    dimmer interior, and variability within an hour [18].
  * Models favour a **MAD flow viewed at low inclination (≲ 30°)**. High inclination (≳ 70°) and
    most SANE models are disfavoured [19].
* **Universality.** The ring size is set by the critical curve, 2√27 M within a few percent for
  any spin [20]. That is why the shadow size in the film should not change with spin.

**GRMHD appearance**, which is inspiration for an animated, volumetric disk:
* **SANE** (weak net field):
  * The disk is MRI-turbulent, geometrically thick (H/r ~ 0.3), and brightest in the disk body
    near the ISCO.
  * Turbulence appears as azimuthally stretched filaments that shear into trailing spirals.
* **MAD** (magnetically arrested) [26, 37]:
  * Accumulated poloidal flux halts the inner flow at ~10–20 r_g. Gas then reaches the hole in
    **narrow spiral streams and plunging streamers** between magnetic "bubbles".
  * The jet is powerful, and its funnel is edge-brightened.
  * **Flux eruptions** recur on ~10³ r_g/c. One estimate is t_rec ≈ 1500 r_g/c [25]. They are
    fed by reconnection in an equatorial current sheet that breaks into **plasmoid chains**.
  * Ejected flux forms low-density, hot **flux tubes or "hot spots"** that orbit at 5–40 r_g,
    somewhat slower than Keplerian [22, 23].
* **Observed hot spots.** GRAVITY tracked Sgr A\* infrared flares moving in a clockwise loop:
  radius about 6–10 r_g, period about 45 ± 15 min, speed about 0.3c [21].
* **Variability with lensing.** During eruptions the photon ring's relative brightness can swing by
  up to 10× at high inclination [24], and every flare echoes in the subrings (§3).

**Visual translation for the disk shader:**
* Advect all noise with Keplerian Ω(r) (plunging velocity inside the ISCO).
* Differential rotation shears features into trailing spirals within one inner orbit. Use two or
  three phase-offset noise layers that re-seed and cross-fade on a period of a few inner orbits.
  This stops the pattern winding up without limit.
* Make turbulent cells anisotropic: radial scale ≈ H, azimuthal scale 5–10× longer.
* Add sparse **hot spots**: Gaussian blobs co-moving at Ω(r), 1.5–3× local emissivity, lifetime
  of 1–2 orbits.
* Add an occasional **flux-eruption event**: an expanding low-density bubble that dims a sector,
  plus a bright reconnection filament. Budget about one per shot.
* Emission inside the ISCO follows §4.3.

---

## 8. Lensing of background stars

* **Weak field (far camera).** The Einstein ring angular radius for sources at infinity and a
  camera at distance d ≫ M is `θ_E ≈ sqrt(4M/d)`: 16° at 50 M, 11.5° at 100 M, 3.6° at 1000 M.
  Compare the shadow radius at 50 M, 5.9° (§2.5). Every star has a **primary image** outside the
  ring and a **secondary image** inside it, always on the opposite side of the centre [1].
  Point-source magnifications, with u = source offset/θ_E, are [39]:
  `μ_± = ½[(u²+2)/(u sqrt(u²+4)) ± 1]`, with total `μ = (u²+2)/(u sqrt(u²+4))`.
  Higher-order (n ≥ 1) relativistic images are demagnified by about e^{−γ} per half-orbit [6] and
  crowd the shadow edge.
* **Strong field and Kerr.** For a rotating hole the Einstein ring becomes a set of **critical
  curves**, whose images on the celestial sphere are small astroid-shaped **caustics** [1]. As a
  star crosses a caustic, its images are created or annihilated in pairs on the critical curve.
  When the camera moves, star images stream around the shadow along closed tracks. Near the
  flattened edge of a fast spinner there are extra images between the critical curves [1].
* **Flux conservation.** Extended sources, such as the diffuse Milky Way and nebulae, keep surface
  brightness (× g⁴ bolometric; `B_ν(ν, gT)` in colour), so sample them directly. **Point stars
  must be magnified by solid angle**: flux_obs = flux_star × μ × g^{3+α}, where
  `μ = (pixel solid angle)/(source solid angle it maps to) = 1/|det J|`. Get J from ray
  differentials, i.e. finite differences between neighbouring pixels' exit directions.
* **Flicker control.** Point stars shimmer when their images cross pixel boundaries.
  * DNGR traced elliptical ray *bundles* (geodesic deviation). It splatted each star with a
    truncated-Gaussian weight, initial beam radius **2 pixel spacings**, sized for at most **2 %**
    brightness variation as a star moves across the pixel grid [1, A.3.1].
  * For motion blur it swept the beam ellipse analytically, not with Monte-Carlo time samples
    [1, A.3.2].
  * Practical equivalent: splat each star as a unit-integral Gaussian (σ ≈ 0.8–1 px) at its mapped
    position, and scale its flux by μ. Clamp μ near critical curves, where it diverges for point
    sources; cap it at ~50, which is physically fine because stars are not points at that
    magnification.

---

## 9. The falling beacon: time dilation and redshift

**Exact Schwarzschild case.** An emitter falls radially from rest at infinity. Photons are
emitted radially outward to a distant observer on the same line:

```
g(r) = 1 − sqrt(2M/r)                         (Doppler × gravitational, exact)
released from rest at r0 (E = sqrt(1 − 2M/r0)):   g(r) = (1 − 2M/r) / ( E + sqrt(E² − 1 + 2M/r) )
observed time:  t_obs = t_em(r) − r*(r) + const,   r* = r + 2M ln(r/2M − 1)
late times:     g ∝ exp(−κ t_obs),   κ = 1/(4M) (Schwarzschild);   Kerr κ = (r_+ − r_-)/(2(r_+² + a²))
```

These are the classic results for a collapsing star [30]. Late-time total light, dominated by
photons that leak off the photon sphere, fades as exp(−t/(3√3 M)).

Beacon falling from rest at infinity (Schwarzschild; t_obs = 0 when the ship is at 20 M; ship
proper time τ):

| r_em (M) | g | 1+z | t_obs (M) | τ_ship (M) |
|---|---|---|---|---|
| 20 | 0.684 | 1.46 | 0 | 0 |
| 10 | 0.553 | 1.81 | 43.2 | 27.3 |
| 6 | 0.423 | 2.37 | 59.3 | 35.2 |
| 4 | 0.293 | 3.41 | 68.0 | 38.4 |
| 3 | 0.184 | 5.45 | 73.5 | 39.7 |
| 2.5 | 0.106 | 9.5 | 77.6 | 40.3 |
| 2.2 | 0.047 | 21 | 82.0 | 40.6 |
| 2.05 | 0.012 | 81 | 88.0 | 40.8 |
| 2.01 | 0.0025 | 400 | 94.5 | 40.8 |

* The ship crosses the horizon 40.8 M of its own time after passing 20 M.
* The outside observer sees the last ~20 M of g stretched into a slide that halves g every
  **4M ln 2 ≈ 2.8 M** and never quite ends.
* For a = 0.8 the e-folding time is 1/κ = 5.33 M.

**Observed pulse period and brightness.**
* A beacon that flashes every Δτ of its own time is seen with period `ΔT_obs ≈ Δτ/g`
  (instantaneous g). The period grows exponentially in the final phase.
* Bolometric flux of a point source falls roughly as g⁴ (energy, arrival rate, and two powers of
  aberration), before extra lensing demagnification. That is about e^{−t/M} late on, so the beacon
  **fades faster than it reddens**.
* After the direct image goes, faint **photon-ring echoes** of the last flashes can appear around
  the shadow edge ~16 M later at ~5 % brightness (§3). This is a physically honest "last signal".

**Real durations scale with mass.** 1/κ = 5.33 GM/c³ for a = 0.8:

| M | 1/κ |
|---|---|
| 10 M_sun | 0.26 ms |
| 10^5 M_sun | 2.6 s |
| 10^6 M_sun | 26 s |
| 4×10^6 M_sun | 105 s |
| 10^9 M_sun | 7.3 h |

**Colour.** A **monochromatic** red LED beacon (650 nm) leaves the visible band once g < 0.93.
A blue 450 nm line lasts only until g ≈ 0.64. A physical line beacon therefore vanishes long
before the dramatic part. Model the beacon as a **hot blackbody strobe** (T ≈ 7000–9000 K)
instead. It is then seen at `T_obs = g T`: white → yellow (g ≈ 0.6) → orange → deep red
(g ≈ 0.2, ~1500 K) → gone. The colour ramp stays continuous and physically correct.

**Rendering it correctly with no special cases.** Integrate the beacon's worldline as a timelike
geodesic with the same KS Hamiltonian (H = −½). Tabulate x_b(T), τ_b(T) and u_b(T). For each
camera ray at step λ, test the ray point x(λ) against the beacon sphere at the **ray's own
coordinate time** T(λ). Emission is `pulse(τ_b(T(λ)))`, coloured with `g = 1/(k·u_b)`.
Freezing, slowing, reddening, fading and the echoes all follow automatically.

---

## 10. Rendering recipe (pseudocode)

### 10.1 Camera launch (Kerr–Schild)

```cpp
Frame cam = tetrad(x_cam, u_cam);                 // Gram–Schmidt with g_{μν}(x_cam), §2.3
for pixel (i,j), subsample s:
    vec3 n = normalize(fwd + tan(fov/2)*((sx)*right + (sy)*up));   // camera-frame unit vector
    vec4 kU = -cam.u + n.x*cam.e_fwd + n.y*cam.e_right + n.z*cam.e_up;  // k^μ, k·u_cam = +1
    vec4 k  = lower(g(x_cam), kU);                 // covariant; E = k.t conserved
    State s = { x = (T_cam, x_cam), k };
    trace(s);
```

### 10.2 Integration (already validated; short checklist)

```cpp
RHS(x,k): see §2.2 (explicit derivatives or dual numbers on H).
Step control (RK4 with displacement bound, or DOPRI5 [33] with rtol~1e-8):
    h = h0 * clamp(r - r_+, 0.02, r) / |dx/dλ|_spatial      // h0 ≈ 0.03–0.05
    near disk slab (|z| < 3H_max and r_in-0.5 < r < r_out): also cap |Δz| ≤ 0.5*H(r)
    in volume: cap |Δx| ≤ voxel/noise feature size
Termination:
    r < r_+ (1 + ε), ε ≈ 1e-2  → captured (black)            // see pitfall P2
    |x| > R_escape (≥ 1e3 M, or 50× camera distance) and dr/dλ > 0 → sample sky with k direction
    steps > N_max (~2e4) → captured (photon-ring limit)
    Tr < 1e-4 → done
Monitor |H|/k_t² ; if > 1e-6, renormalize: solve for scalar s so that H(k_t, s·k_i) = 0.
```

### 10.3 Disk plane and volume

```cpp
// thin sheet: detect sign change of z between steps
if (z_prev*z < 0) {
    double f = z_prev/(z_prev - z);                // or 2–3 Newton/secant refinements on z(λ)
    State c = lerp(prev, cur, f);
    double r = sqrt(max(c.x*c.x + c.y*c.y - a*a, 0.0));
    if (r >= r_in && r <= r_out) shade_disk(c, r);   // front-to-back composite, then continue
}
// volumetric slab: ray-march while |z| < z_top(r), sub-stepping to Δz ≤ H/2
for each sub-step ds:
    Emitter u = (r >= r_isco) ? circular(r) : plunging(r);   // §2.3, §4.3
    double g = 1.0 / dot(k, u);                               // §5.1
    double dl = dλ / g;                                       // gas-frame length
    // time-dependent textures at emission time T(λ); pattern phase Φ − Ω(r)·T
    rho = density(r, z, Φ - Ω*T, T);  Te = T_profile(r) * tempNoise(...);
    dtau = kappa * rho * dl;
    rgb += Tr * (1 - exp(-dtau)) * colour(g_c*Te) * brightness(Te) * pow(g, p);   // §6 controls
    Tr  *= exp(-dtau);
```

Use KS Φ = atan2(y,x) − atan2(a, r) as the disk azimuth. It is regular through the horizon, and
circular orbits obey dΦ/dT = Ω exactly. Never use Boyer–Lindquist φ inside the ISCO, because
∫a/Δ dr diverges at r_+.

### 10.4 g-factor for any emitter

```cpp
double gfactor(vec4 k_cov, vec4 u_em_contra) { return 1.0 / dot(k_cov, u_em_contra); } // k·u_cam = 1
// circular:  u = ut*(ξ_t + Ω ξ_φ)    → k·u = ut*(k_t + Ω*(x*k_y - y*k_x))
// plunging:  u = uT ξ_t + uΦ ξ_φ + u^r (l_x,l_y,l_z)  (§4.3)
// beacon:    u from its integrated worldline
```

### 10.5 Pitfalls

* **P1 – r(x,y,z) cancellation.** When w < 0 (near the ring |z| → 0, x² + y² < a²), use the
  stable root in §2.1. Clamp r ≥ 1e-6. Rays never legitimately get there anyway.
* **P2 – past horizon.** Ingoing KS is regular on the *future* horizon. A ray traced backward from
  the camera toward the hole asymptotes to the *past* horizon, which sits at T = −∞ in these
  coordinates. So r approaches r_+ from outside without crossing, and |k_μ| and |dT/dλ| grow
  exponentially. This is harmless if you stop at r < r_+(1+ε) and cap the step count.
  * Physically these pixels are black: nothing comes out of the past horizon.
  * Do not use Boyer–Lindquist, where Δ → 0 blows up the equations.
  * Outgoing KS coordinates would make the past horizon regular, but they are unnecessary.
* **P3 – photon-ring rays.** Near-critical rays can orbit 2–4 times before leaving. Too large a
  step there makes the ring jagged or shifts it by a pixel. Use the displacement bound plus a
  minimum of about 50 steps per half-orbit. Validate that the traced critical curve matches §2.5
  to better than 0.01 M.
* **P4 – thin-slab skipping.** A large step can jump over the H ≈ 0.03 r slab near the plane.
  Always cap |Δz| near the plane (§10.2) and detect sheet crossings by sign change.
* **P5 – constraint drift.** With RK4 and these steps, |H|/E² should stay below about 1e-8 per
  ray. Drift above 1e-6 means bad steps; renormalize as in §10.2 and log it. The conserved k_t and
  L are free checks.
* **P6 – precision.** Use doubles throughout. Cameras at 10^3–10^4 M are fine, and step size ∝ r
  keeps the far-field cost logarithmic. Do not add `T` offsets to huge scene times in float;
  store the time since the shot start.
* **P7 – time sampling.** An animated disk must be sampled at the ray's T(λ), not the frame time.
  Otherwise the subrings, the far side, and the beacon echoes are wrong by ~10–30 M of light
  travel time.
* **P8 – colour.** Shift temperature (B(ν, gT)), not RGB. Tone-map only at the end.

---

## 11. Recommendations for the film

**1. Spin a = 0.8.** Acceptable range 0.7–0.85.
* **Shadow.** The shadow is offset 1.7 M (16 % of its diameter) toward the receding side, and its
  approaching edge is flattened by about 9 % (§2.5). That is a visible Kerr signature without
  DNGR's "confusing" D-shape and the extra image strips alongside a flat edge; that problem
  appears at a ≳ 0.9 [1].
* **Disk.** The ISCO at 2.91 M brings the inner disk edge tight against the photon ring (the
  lensing ring sits at about 5.2–5.5 M on screen). This packs the brightest structure close to the
  shadow.
* **Temperature.** The peak is at 4.4 M, so the hot band sits just outside the ring.
* **Other spins.** a = 0.6 (Interstellar) reads almost Schwarzschild. At a ≥ 0.95 the NHEK
  structure and the sliver-thin inner disk look like artifacts at film resolution.

**2. Reveal at i = 80°** (75–84°).
* The far side of the disk lifts over the top of the shadow into the iconic arch, and the n = 1
  image hugs the underside.
* The direct disk crosses the shadow as a thin band (aspect cos 80° ≈ 0.17).
* **Above ~86°** the direct disk collapses to a line and the arch dominates. Use this for the
  skim-over shot S4.
* **Below ~70°** the arch detaches and the look becomes EHT-like.
* Put the spin axis near vertical (tilted ≤ 10°), with the approaching side on screen left.

**3. Disk extent.**
* Inner edge at the ISCO (2.91 M) with the plunging-region veil (§4.3) down toward r_+.
* Outer emissive edge at 30 M, tapered with smoothstep from 18 M to 30 M.
* Faint wisps can extend to ~50 M for scale.
* In the frame the disk should reach about 2.5–3× the shadow diameter on each side.

**4. Temperature and colour.**
* Page–Thorne shape (§4.2) with emitted **T_peak = 6500 K at r ≈ 4.4 M** and camera **white
  balance 6500 K**. This gives, at i = 80°:
  * approaching side at 4–6 M: 8.7–9.0 kK, **blue-white**;
  * far and near sides (g ≈ 0.75–0.9): 4.9–5.9 kK, **white-gold**;
  * receding side: 2.6–3.2 kK, **amber**.
* Inner edge and plunging region: deep red.
* The outer disk falls to 3 kK by 20 M, which reads as a dark red rim. If it is too dark, flatten
  the outer profile to T ∝ r^{−1/2} beyond ~8 M. That is the profile of a flared, irradiated disk,
  which is a defensible physical excuse.

**5. Beaming.**
* Physical colour shift (q = 1, or 0.85 if hues look too saturated).
* Brightness ∝ luminance-normalized × **g^2**. This gives 12× approach/recede contrast at the
  temperature peak, versus about 1400× in visual luminance physically.
* For one "true physics" beat (e.g. S5 push-in), ramp p toward 3–4 and let the receding side die.

**6. Thickness.** Core H/r = 0.03, optically thick (vertical τ ≈ 5). Turbulent, optically thin
atmosphere to |z| ≈ 0.1 r. Disk turbulence, hot spots and flux eruptions as in §7.

**7. Photon ring.** Let it emerge from the integration; do not paint it. Requirements:
* sample rays by T(λ);
* ≥ 50 steps per half-orbit near the shell;
* adaptive supersampling in the ring band (|b − b_crit| < 0.3 M on screen).

At hero framings, expect the lensing ring (n = 1) plus a 2–5 px n = 2 line. A small (≤ 1.5×) gain
on n ≥ 2 contributions, tagged by crossing count, is an acceptable grading choice (§12).

**8. Integrator.**
* Keep the validated KS Hamiltonian RK4 with displacement-bounded steps.
* Add the slab |Δz| cap, horizon ε = 1e-2, a 2e4 step cap, and H monitoring.
* Optional: DOPRI5 with rtol 1e-8 for stills and verification renders.
* Regression-test against §2.5 (shadow edges), §6 (g-values) and §3 (e^{−γ} width ratios).

**9. Beacon climax.**
* Hot-blackbody strobe (§9) on a real geodesic.
* Choose the scene mass or a time-remap so that 1/κ ≈ 1.5–2.5 s of screen time. The physical
  1/κ is 2.6 s at 10^5 M_sun, or 105 s at Sgr A\* mass.
* Pulses stretch as 1/g. Include the photon-ring echo of the final flash.

**10. Lens and post.** Veiling flare is a real-camera effect that DNGR added on purpose [1]. It is
fine as long as it never fills the shadow above the scene's black level.

---

## 12. Film choices and departures from physics

| # | Choice | Physics | Why we depart | Size of departure |
|---|---|---|---|---|
| D1 | Disk glows at 2.5–9 kK in visible light | Thin disks around SMBHs peak at 10^4.5–10^5.5 K (UV). Visible T needs impossible M or a near-dead disk | Visible, cinematic palette; Interstellar did the same (4500 K) [1] | T scale × ~10⁻¹ |
| D2 | Beaming brightness ∝ g^2 | g⁴ bolometric; ~10³ in visual luminance near the ISCO | Keep the receding side readable | Contrast 12× instead of ~150–1400× at the peak |
| D3 | Colour shift kept (q ≈ 0.85–1) | q = 1 | Hue swing slightly softened if needed | ≤ 15 % in log T |
| D4 | Outer disk T ∝ r^{−1/2} beyond ~8 M (optional) | Page–Thorne ∝ r^{−3/4} | Keep the outer disk visible | T(30 M) +30 % |
| D5 | Plunging-region glow 3–8 % | Novikov–Thorne: zero; MHD: small, nonzero [13, 14] | Visual continuity to the ring | Within the MHD range |
| D6 | Disk turbulence, hot spots, eruptions time-compressed | Inner orbit 36 M ≈ 3 min at 10^6 M_sun; eruptions every ~10³ M | Motion must read in a 90 s film | Speed-up ×10–100, stated per shot |
| D7 | Thin-but-volumetric disk (H/r 0.03–0.1) with visible-light turbulence | Efficient thin disks have H/r ~ 0.01; EHT-type flows are thick and radio-bright | Texture and depth | Stylised |
| D8 | Camera sky Doppler and aberration from camera motion may be suppressed (static or ZAMO launch frame while the camera moves) | Aberration is large at v ≳ 0.1c [1] | Avoid a distracting sky "warp" in moves that are not the story | Only in shots marked "non-physical camera" |
| D9 | n ≥ 2 photon-ring gain ≤ 1.5× | Exact from integration | Legibility on small screens | Grading only |
| D10 | Veiling flare, bloom, anamorphic streak | Not part of the spacetime | Continuity with real camera footage [1] | Post |
| D11 | Beacon blackbody strobe; 1/κ mapped to ~2 s | Physical 1/κ = 5.33 GM/c³ | Pacing | Mass choice or time-remap |
| D12 | Star magnification capped at μ ≤ 50; stars splatted as Gaussians | Point sources diverge on critical curves | Flicker and aliasing [1] | Only at caustic crossings |

No departure changes the **geometry**. Shadow size and shape, lensed disk images, ring nesting,
time delays and the direction of beaming are all exact.

---

### 12.1 As built (production/, 2026-09-29)

What the renderer actually does, and where it departs:

| # | choice in the code | physics | why |
|---|---|---|---|
| P1 | spin a = 0.8, camera at 86° for the approach and reveal, 88.8–89.5° for grazing shots | — | §11 recommendation; near-edge-on gives the iconic lensed arch |
| P2 | emitted peak 6500 K (Page–Thorne profile, T ∝ F^1/4, warm floor near the ISCO); white balance 6500 K | real disks peak at 10^4.5–10^5.5 K | visible-light palette: white-gold inside, amber outside |
| P3 | observed colour temperature = T·g (physical); intensity ∝ (T/T_peak)^4 · g^2 | bolometric g^4 | beaming kept readable (≈7–12× contrast instead of 150×+) |
| P4 | turbulence advected at Keplerian Ω(r), two flow layers reset every 0.35 local orbits and cross-faded | real flow never resets | avoids the "vinyl record" over-shear; per-radius reset (Neyret 2003) |
| P5 | disk clock: 1.4 M per film second (≈25 s per ISCO orbit on screen) | for a 10^6–10^9 M☉ hole an ISCO orbit takes minutes to days | the disk must visibly live but stay stately |
| P6 | S15 infall: exact timelike geodesic in Kerr–Schild coordinates; the camera clock runs at 5 M per film second, decoupled from the disk clock | one clock for everything | the fall must happen inside 6.5 s of screen time; invisible to an audience |
| P7 | beacon = Gaussian emissive blob σ = 0.08 M (much larger than a ship) with pulses in proper time; redshift and delays from the ray tracing itself | a point source | readable glow at 55 M; lensed images, light-travel delays and stretching are physical |
| P8 | back-traced rays below the prograde photon orbit and still falling are called captured | exact (no turning point) | avoids the ingoing-Kerr–Schild horizon pile-up |
| P9 | star brightness 10^(−0.4·0.8·V) (magnitudes compressed by 0.8) | 10^(−0.4·V) | a dense natural-looking field on a phone screen |
| P10 | sky Doppler/gravitational shift applied as intensity g^(4·s), s = 1 (0.6 in S13) | g^4 | S13's aberration is physical; the brightening is tempered |
| P11 | ship and debris rendered in flat space (Blender) and lit by an equirect probe traced from the ship's position | the ship sits in curved space | at ship scale the metric is flat; lighting keeps the lensed disk light |
| P12 | LSV-7 ion thrusters sit behind the reactor on its unshielded side; radiators only roughly inside the shield's shadow cone | a real design puts them in the shield's shadow | silhouette and readability |
| P13 | the xenon strobe is far brighter than a real beacon | real beacons are faint | it lights the foil and reads at distance |
| P14 | ion plumes glow visibly | nearly invisible in reality | a thread of blue engine light sells scale in S11/S12 |

## 13. References

1. O. James, E. von Tunzelmann, P. Franklin, K. S. Thorne, "Gravitational lensing by spinning black holes in astrophysics, and in the movie *Interstellar*", CQG 32, 065001 (2015). [arXiv:1502.03808](https://arxiv.org/abs/1502.03808), [doi:10.1088/0264-9381/32/6/065001](https://doi.org/10.1088/0264-9381/32/6/065001) ([Consensus](https://consensus.app/papers/details/97ae50e7dc0651bda0f0db622bb3040e/?utm_source=claude_desktop))
2. J. M. Bardeen, "Timelike and null geodesics in the Kerr metric", in *Black Holes (Les Houches 1972)*, eds. C. & B. DeWitt, Gordon & Breach, p. 215 (1973).
3. J. M. Bardeen, W. H. Press, S. A. Teukolsky, "Rotating black holes: locally nonrotating frames, energy extraction, and scalar synchrotron radiation", ApJ 178, 347 (1972). [doi:10.1086/151796](https://doi.org/10.1086/151796)
4. B. Carter, "Global structure of the Kerr family of gravitational fields", Phys. Rev. 174, 1559 (1968). [doi:10.1103/PhysRev.174.1559](https://doi.org/10.1103/PhysRev.174.1559)
5. S. E. Gralla, A. Lupsasca, "Null geodesics of the Kerr exterior", PRD 101, 044032 (2020). [arXiv:1910.12881](https://arxiv.org/abs/1910.12881), [doi:10.1103/PhysRevD.101.044032](https://doi.org/10.1103/PhysRevD.101.044032) ([Consensus](https://consensus.app/papers/details/9d18af9ec1b75df6a709403af1eda215/?utm_source=claude_desktop))
6. S. E. Gralla, A. Lupsasca, "Lensing by Kerr black holes", PRD 101, 044031 (2020). [arXiv:1910.12873](https://arxiv.org/abs/1910.12873), [doi:10.1103/PhysRevD.101.044031](https://doi.org/10.1103/PhysRevD.101.044031) ([Consensus](https://consensus.app/papers/details/6bf3a6d278d85b0fab2ee178d40635c7/?utm_source=claude_desktop))
7. M. D. Johnson et al., "Universal interferometric signatures of a black hole's photon ring", Sci. Adv. 6, eaaz1310 (2020). [arXiv:1907.04329](https://arxiv.org/abs/1907.04329), [doi:10.1126/sciadv.aaz1310](https://doi.org/10.1126/sciadv.aaz1310) ([Consensus](https://consensus.app/papers/details/f73ecc05324a5df5b5f7bca6a8ce4aa6/?utm_source=claude_desktop))
8. S. E. Gralla, D. E. Holz, R. M. Wald, "Black hole shadows, photon rings, and lensing rings", PRD 100, 024018 (2019). [arXiv:1906.00873](https://arxiv.org/abs/1906.00873)
9. I. D. Novikov, K. S. Thorne, "Astrophysics of black holes", in *Black Holes (Les Astres Occlus)*, eds. C. & B. DeWitt, Gordon & Breach, p. 343 (1973).
10. D. N. Page, K. S. Thorne, "Disk-accretion onto a black hole. Time-averaged structure of accretion disk", ApJ 191, 499 (1974). [doi:10.1086/152990](https://doi.org/10.1086/152990)
11. C. T. Cunningham, "The effects of redshifts and focusing on the spectrum of an accretion disk around a Kerr black hole", ApJ 202, 788 (1975). [doi:10.1086/154033](https://doi.org/10.1086/154033)
12. J.-P. Luminet, "Image of a spherical black hole with thin accretion disk", A&A 75, 228 (1979).
13. Y. Zhu, S. W. Davis, R. Narayan, A. K. Kulkarni, R. F. Penna, J. E. McClintock, "The eye of the storm: light from the inner plunging region of black hole accretion discs", MNRAS 424, 2504 (2012). [arXiv:1202.1530](https://arxiv.org/abs/1202.1530)
14. A. Mummery et al., "Continuum emission from within the plunging region of black hole discs", MNRAS (2024). [arXiv:2405.09175](https://arxiv.org/abs/2405.09175)
15. Event Horizon Telescope Collaboration, "First M87 Event Horizon Telescope Results. I. The shadow of the supermassive black hole", ApJL 875, L1 (2019). [arXiv:1906.11238](https://arxiv.org/abs/1906.11238), [doi:10.3847/2041-8213/ab0ec7](https://doi.org/10.3847/2041-8213/ab0ec7)
16. EHT Collaboration, "… V. Physical origin of the asymmetric ring", ApJL 875, L5 (2019). [arXiv:1906.11242](https://arxiv.org/abs/1906.11242), [doi:10.3847/2041-8213/ab0f43](https://doi.org/10.3847/2041-8213/ab0f43)
17. EHT Collaboration, "… VI. The shadow and mass of the central black hole", ApJL 875, L6 (2019). [arXiv:1906.11243](https://arxiv.org/abs/1906.11243), [doi:10.3847/2041-8213/ab1141](https://doi.org/10.3847/2041-8213/ab1141)
18. EHT Collaboration, "First Sagittarius A\* Event Horizon Telescope Results. I. The shadow of the supermassive black hole in the center of the Milky Way", ApJL 930, L12 (2022). [arXiv:2311.08680](https://arxiv.org/abs/2311.08680), [doi:10.3847/2041-8213/ac6674](https://doi.org/10.3847/2041-8213/ac6674)
19. EHT Collaboration, "First Sagittarius A\* EHT Results. V. Testing astrophysical models of the Galactic Center black hole", ApJL 930, L16 (2022). [arXiv:2311.09478](https://arxiv.org/abs/2311.09478)
20. T. Johannsen, D. Psaltis, "Testing the no-hair theorem with observations in the electromagnetic spectrum. II. Black hole images", ApJ 718, 446 (2010). [arXiv:1005.1931](https://arxiv.org/abs/1005.1931)
21. GRAVITY Collaboration, "Detection of orbital motions near the last stable circular orbit of the massive black hole SgrA\*", A&A 618, L10 (2018). [arXiv:1810.12641](https://arxiv.org/abs/1810.12641)
22. B. Ripperda et al., "Black hole flares: ejection of accreted magnetic flux through 3D plasmoid-mediated reconnection", ApJL 924, L32 (2022). [arXiv:2109.15115](https://arxiv.org/abs/2109.15115)
23. O. Porth et al., "Flares in the Galactic Centre – I. Orbiting flux tubes in magnetically arrested black hole accretion discs", MNRAS (2021). [Consensus](https://consensus.app/papers/details/e395e6681f8651e7a811e8577d07ec7e/?utm_source=claude_desktop)
24. Z. Gelles et al., "Relativistic signatures of flux eruption events near black holes", Galaxies (2022). [Consensus](https://consensus.app/papers/details/d673fa723a86542abd2e1c47b510b603/?utm_source=claude_desktop)
25. J. Jacquemin-Ide et al., "Demystifying flux eruptions: magnetic flux transport in magnetically arrested disks", ApJ (2025). [Consensus](https://consensus.app/papers/details/057eee2ca2195265846e5158d488b2cc/?utm_source=claude_desktop)
26. R. Narayan, I. V. Igumenshchev, M. A. Abramowicz, "Magnetically arrested disk: an energetically efficient accretion flow", PASJ 55, L69 (2003). [arXiv:astro-ph/0305029](https://arxiv.org/abs/astro-ph/0305029)
27. M. Visser, "The Kerr spacetime: a brief introduction" (2007). [arXiv:0706.0622](https://arxiv.org/abs/0706.0622)
28. C.-K. Chan, D. Psaltis, F. Özel, "GRay: a massively parallel GPU-based code for ray tracing in relativistic spacetimes", ApJ 777, 13 (2013). [arXiv:1303.5057](https://arxiv.org/abs/1303.5057)
29. M. Mościbrodzka, C. F. Gammie, "ipole – semianalytic scheme for relativistic polarized radiative transport", MNRAS 475, 43 (2018). [arXiv:1712.03057](https://arxiv.org/abs/1712.03057)
30. W. L. Ames, K. S. Thorne, "The optical appearance of a star that is collapsing through its gravitational radius", ApJ 151, 659 (1968). [doi:10.1086/149465](https://doi.org/10.1086/149465)
31. J. L. Synge, "The escape of photons from gravitationally intense stars", MNRAS 131, 463 (1966). [doi:10.1093/mnras/131.3.463](https://doi.org/10.1093/mnras/131.3.463)
32. K. Hioki, K. Maeda, "Measurement of the Kerr spin parameter by observation of a compact object's shadow", PRD 80, 024042 (2009). [arXiv:0904.3575](https://arxiv.org/abs/0904.3575)
33. J. R. Dormand, P. J. Prince, "A family of embedded Runge–Kutta formulae", J. Comput. Appl. Math. 6, 19 (1980). [doi:10.1016/0771-050X(80)90013-3](https://doi.org/10.1016/0771-050X(80)90013-3)
34. G. B. Rybicki, A. P. Lightman, *Radiative Processes in Astrophysics*, Wiley (1979), §1.3–1.4 and §4.9 (I_ν/ν³ invariance).
35. C. W. Misner, K. S. Thorne, J. A. Wheeler, *Gravitation*, Freeman (1973), §22.6 (kinetic theory and Liouville in curved spacetime) and §33 (Kerr geodesics).
36. N. I. Shakura, R. A. Sunyaev, "Black holes in binary systems. Observational appearance", A&A 24, 337 (1973).
37. A. Tchekhovskoy, R. Narayan, J. C. McKinney, "Efficient generation of jets from magnetically arrested accretion on a rapidly spinning black hole", MNRAS 418, L79 (2011). [arXiv:1108.0412](https://arxiv.org/abs/1108.0412)
38. C. Wyman, P.-P. Sloan, P. Shirley, "Simple analytic approximations to the CIE XYZ color matching functions", JCGT 2(2) (2013).
39. B. Paczyński, "Gravitational microlensing by the galactic halo", ApJ 304, 1 (1986). [doi:10.1086/164140](https://doi.org/10.1086/164140)
40. V. Bozza, "Gravitational lensing by black holes", Gen. Rel. Grav. 42, 2269 (2010). ([Consensus](https://consensus.app/papers/details/9f70d165b92c539ab48ad2ff87b28178/?utm_source=claude_desktop))
