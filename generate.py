"""
Ender 5 / Ender 5 S1 webcam mount — T-shaped 2020 bracket + printed 1/4"-20 thumbscrew.

Generates two parts:
  * a T-plate: a crossbar that bolts along a 2020 rail with two M3 T-nuts, and
    an arm reaching out perpendicular to it with a 1/4"-20 through-hole for the
    camera. A rib along the arm keeps the cantilever from drooping.
  * a knurled 1/4"-20 thumbscrew, so no metal tripod screw is needed.

Design notes, all of them learned by building the wrong thing first:

  * T-SHAPE, not in-line. A 2020's slots all run along the extrusion, so two
    bolts on one face can only ever be collinear with the rail. Turning the ARM
    90 deg relative to the bolt line is what lets it reach away from the rail.
  * THROUGH-HOLE + SCREW, not an integrated post. A post long enough to feel
    solid bottoms out in the camera's tripod socket before the camera seats,
    and a fixed post cannot clamp the camera at a chosen rotation.
  * FLAT by default. Most webcam arms have their own tilt/Z adjustment, so a
    built-in dip mostly just fights them. --tilt exists but is rarely wanted.
  * SHORT THREAD. Tripod sockets bottom out around 5-6 mm, so the thread is
    plate thickness + SOCKET_ENGAGE and no more. Longer is worse, not better.
  * RIB ON TOP, same side as the crossbar. That keeps the whole underside flat,
    so it is simultaneously the mounting face and a support-free print face.

Usage:
    python3 generate.py                 # flat T-plate + thumbscrew
    python3 generate.py --tilt 5        # tapered 5 deg (plate starts thicker)
    python3 generate.py --bolt m5       # M5 T-nuts instead of M3

Needs: trimesh, manifold3d (CSG backend), numpy.
Licence: CC BY 4.0.
"""
import argparse
import collections

import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix

# ---- plate (mm) -------------------------------------------------------------
# Longer than v1 (74 -> 105) so the camera reaches out past the top extruder
# rail instead of being crowded by it.
PLATE_L, PLATE_W, PLATE_T = 105.0, 24.0, 4.0
BOLT_D = 3.4              # M3 clearance for the roll-in T-nuts on hand
BOLT_SPACING = 24.0       # along the rail; T-nuts slide so this is not critical
BOLT_INSET = 13.0         # from the mounting end to the first bolt
CAM_D = 6.8               # 1/4"-20 clearance (verified good on the last print)
CAM_INSET = 13.0          # from the far end to the camera hole

# ---- T crossbar + reinforcement ---------------------------------------------
# T-SHAPE: the bolt holes sit on a crossbar running ALONG the rail, while the
# arm reaches out perpendicular to it. A 2020's slots all run along the
# extrusion, so two bolts on one face can only ever be collinear with the rail
# -- the T is what lets the arm point away from it.
# The crossbar doubles as the reinforced pad: it is the cantilever ROOT, where
# the camera's weight over the whole arm becomes bending moment.
CROSS_L, CROSS_W, CROSS_T = 56.0, 26.0, 9.0   # X span (along rail), Y depth, thickness
PAD_L, PAD_W, PAD_T = CROSS_W, CROSS_L, CROSS_T   # aliases used by the ramp
RIB_W, RIB_H = 7.0, 5.0                   # rib along the arm (on TOP, see below)
RIB_END_GAP = 18.0                        # stop short of the camera hole

# ---- printed 1/4"-20 thumbscrew ---------------------------------------------
THREAD_MAJOR = 6.35
THREAD_PITCH = 1.27
THREAD_SHAVE = 0.25       # VALIDATED: operator called this fit "perfect"
SOCKET_ENGAGE = 4.0       # 1 mm shorter than v1 at operator's request; v1 (5 mm)
                          # fitted well, this just guarantees no bottoming out.
HEAD_D, HEAD_T = 20.0, 5.0
KNURLS = 8
SEG = 64


def hole_stats(mesh):
    c = collections.Counter()
    for f in mesh.faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            c[(min(a, b), max(a, b))] += 1
    return sum(1 for v in c.values() if v == 1), sum(1 for v in c.values() if v > 2), len(c)


def thread(length):
    """Helical 1/4-20 ridge on a core cylinder, base at z=0."""
    r_maj = THREAD_MAJOR / 2.0 - THREAD_SHAVE
    r_min = r_maj - 0.61 * THREAD_PITCH
    turns = length / THREAD_PITCH
    n = max(8, int(turns * 48))
    v, f = [], []
    for i in range(n + 1):
        fr = i / n
        th = fr * turns * 2.0 * np.pi
        z = fr * length
        c, s = np.cos(th), np.sin(th)
        v += [[r_min * c, r_min * s, z - THREAD_PITCH / 2.0],
              [r_maj * c, r_maj * s, z],
              [r_min * c, r_min * s, z + THREAD_PITCH / 2.0]]
    for i in range(n):
        a, b = 3 * i, 3 * (i + 1)
        for k in range(3):
            k2 = (k + 1) % 3
            f += [[a + k, b + k, b + k2], [a + k, b + k2, a + k2]]
    f.append([0, 1, 2])
    f.append([3 * n + 2, 3 * n + 1, 3 * n])
    ridge = trimesh.Trimesh(vertices=np.array(v), faces=np.array(f), process=True)
    core = trimesh.creation.cylinder(radius=r_min + 0.05, height=length, sections=SEG)
    core.apply_translation((0, 0, length / 2.0))
    return trimesh.boolean.union([core, ridge])


def thumbscrew(plate_t=PLATE_T):
    """Knurled head + thread just long enough: plate + socket engagement."""
    tl = plate_t + SOCKET_ENGAGE
    head = trimesh.creation.cylinder(radius=HEAD_D / 2.0, height=HEAD_T, sections=SEG)
    head.apply_translation((0, 0, HEAD_T / 2.0))
    # finger grip: scallop the rim so it can be turned without a tool
    cuts = []
    for i in range(KNURLS):
        a = 2 * np.pi * i / KNURLS
        c = trimesh.creation.cylinder(radius=2.2, height=HEAD_T * 3, sections=32)
        c.apply_translation((np.cos(a) * HEAD_D / 2.0, np.sin(a) * HEAD_D / 2.0, HEAD_T / 2.0))
        cuts.append(c)
    head = trimesh.boolean.difference([head, trimesh.boolean.union(cuts)])
    th = thread(tl)
    th.apply_translation((0, 0, HEAD_T))
    return trimesh.boolean.union([head, th]), tl


def plate(tilt_deg=0.0):
    # A tapered plate must START thicker, or the wedge cuts straight through:
    # 5 deg over 74 mm needs 6.47 mm of drop, which a flat 4 mm plate does not
    # have. So PLATE_T is the CAMERA-END thickness and the mount end is raised
    # by the drop. (At 0 deg this is just a flat PLATE_T plate.)
    drop = np.tan(np.radians(tilt_deg)) * PLATE_L if tilt_deg else 0.0
    thick = PLATE_T + drop

    body = trimesh.creation.box(extents=(PLATE_W, PLATE_L, thick))
    body.apply_translation((0, PLATE_L / 2.0, thick / 2.0))

    # --- reinforcement, added BEFORE the holes so the bolts pass through it ---
    # Mounting pad: wider and thicker at the root, where bending peaks.
    # The T crossbar: long along X (the rail), shallow in Y, thick for strength.
    pad = trimesh.creation.box(extents=(CROSS_L, CROSS_W, CROSS_T))
    pad.apply_translation((0, CROSS_W / 2.0, CROSS_T / 2.0))

    # Ramp the pad's top down into the arm so there is no abrupt step to crack
    # at. Two things this must get right, both of which bit earlier versions:
    #   - the cutting plane must DESCEND with +y (negative rotation), otherwise
    #     it shaves the whole pad away instead of just its far end;
    #   - it must be BOUNDED to the transition zone, otherwise it keeps
    #     descending and slices the arm off beyond the pad.
    ramp_run = (PAD_T - thick) / np.tan(np.radians(28.0))
    cutter = trimesh.creation.box(extents=(PAD_W * 4, PAD_L * 4, PAD_T * 6))
    cutter.apply_translation((0, 0, PAD_T * 3))
    cutter.apply_transform(rotation_matrix(-np.radians(28.0), [1, 0, 0], [0, PAD_L, thick]))
    limiter = trimesh.creation.box(extents=(PAD_W * 4, ramp_run, PAD_T * 6))
    limiter.apply_translation((0, PAD_L - ramp_run / 2.0, 0))
    pad = trimesh.boolean.difference([pad, trimesh.boolean.intersection([cutter, limiter])])
    body = trimesh.boolean.union([body, pad])

    # Stiffening rib: turns a floppy 4 mm strip into a stiff beam.
    # It goes on TOP, on the same side as the pad, for two reasons:
    #   - the whole underside then stays FLAT, so the mounting face seats
    #     properly on the rail AND the part prints face-down with no supports;
    #   - it still clears the camera, which sits at y=PLATE_L-CAM_INSET while
    #     the rib stops well short of it.
    rib_start = PAD_L
    rib_len = (PLATE_L - CAM_INSET - RIB_END_GAP) - rib_start
    rib = trimesh.creation.box(extents=(RIB_W, rib_len, RIB_H))
    rib.apply_translation((0, rib_start + rib_len / 2.0, thick + RIB_H / 2.0))
    body = trimesh.boolean.union([body, rib])

    if tilt_deg:
        # Shave a shallow wedge off the top so the camera end sits lower.
        # Rotate NEGATIVE: the cutting plane must DIP as y grows so it shaves
        # the top of the camera end. A positive angle lifts the plane clear of
        # the plate and silently removes nothing.
        big = 400.0
        wedge = trimesh.creation.box(extents=(big, big, big))
        wedge.apply_translation((0, 0, big / 2.0 + thick))
        wedge.apply_transform(rotation_matrix(-np.radians(tilt_deg), [1, 0, 0],
                                              [0, 0, thick]))
        body = trimesh.boolean.difference([body, wedge])

    cuts = []
    # Both bolts sit on the crossbar, spaced along X so they land in ONE rail slot.
    for x in (-BOLT_SPACING / 2.0, BOLT_SPACING / 2.0):
        c = trimesh.creation.cylinder(radius=BOLT_D / 2.0, height=CROSS_T * 8, sections=SEG)
        c.apply_translation((x, CROSS_W / 2.0, CROSS_T / 2.0))
        cuts.append(c)
    c = trimesh.creation.cylinder(radius=CAM_D / 2.0, height=thick * 8, sections=SEG)
    c.apply_translation((0, PLATE_L - CAM_INSET, thick / 2.0))
    cuts.append(c)
    return trimesh.boolean.difference([body, trimesh.boolean.union(cuts)])


def report(m, label, path):
    b, nm, tot = hole_stats(m)
    if b:
        raise SystemExit(f"ERROR: {path} has {b} boundary edges — do not print")
    e = m.extents
    print(f"{label}")
    print(f"   closed solid : {b == 0}   non-manifold: {nm}/{tot}")
    print(f"   size         : {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm")
    print(f"   volume       : {m.volume/1000.0:.2f} cm^3 (~{m.volume/1000.0*1.27:.1f} g PLA)")
    print(f"   wrote        : {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tilt", type=float, default=0.0,
                    help="downward wedge in degrees; operator says 0-5 is right")
    ap.add_argument("--prefix", default="ender5-camera-flatplate")
    a = ap.parse_args()

    p = plate(a.tilt)
    p.apply_translation((0, 0, -p.bounds[0][2]))
    pf = f"{a.prefix}_tilt{a.tilt:g}.stl"
    p.export(pf)
    report(trimesh.load(pf), f"PLATE (tilt {a.tilt:g} deg)", pf)

    s, tl = thumbscrew()
    sf = f"{a.prefix}_thumbscrew.stl"
    s.export(sf)
    report(trimesh.load(sf), f"THUMBSCREW (thread {tl:.1f} mm = {PLATE_T:.0f} plate + {SOCKET_ENGAGE:.0f} into camera)", sf)


if __name__ == "__main__":
    main()
