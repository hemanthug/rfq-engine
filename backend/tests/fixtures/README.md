# Real STEP Fixture Policy

This directory is intentionally empty until real STEP files are added.

Do not add mocked geometry, generated placeholder analysis, or test files that
pretend to exercise OpenCascade without being parsed by OpenCascade.

Recommended fixtures:

- Simple rectangular block
- Cylinder
- Plate with a through-hole
- Block with a blind hole
- Multi-body or assembly-style STEP file
- Invalid or unsupported file for negative parser tests

Fixture-based tests should compare real OpenCascade-computed values with
tolerances. They should not assert against fake extraction results.

Included public fixture:

- `step_tools_io1_ug_214.stp`: STEP Tools AP214 sample file `io1-ug-214.stp`,
  downloaded from `https://steptools.com/docs/stpfiles/ap214/`.
- `flx-4589.stp`: real shaft fixture used as a regression case where repeated
  tooth/flank cylindrical faces must not be classified as CNC holes.
- `HTD5M-20W-48Z-D20.STEP`: real pulley fixture used as a regression case where
  repeated tooth/root cylindrical arcs must not be classified as CNC holes.
