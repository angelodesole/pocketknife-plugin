# pkClipCurves

Clips curves with mask shapes, like a clipping mask: curves are cut where they cross the mask boundaries and only the pieces inside (or outside) are kept. First select the curves to clip, then the mask shapes.

| Option | Effect |
|---|---|
| `Keep=Inside` | Keeps the pieces inside the masks (default). |
| `Keep=Outside` | Keeps the pieces outside the masks. |
| `DeleteMask=No` | Keeps the mask objects (default). |
| `DeleteMask=Yes` | Deletes the mask objects. |

## Notes

Masks are closed planar curves and hatches, all on one plane; masks on different planes stop the command without changing anything. Even-odd rule: nested shapes are holes. Stretches lying on a mask boundary are always dropped (no double laser pass); a curve that only touches the boundary is not split. Curves off the mask plane are clipped by their projection along the mask normal and stay where they are. One undo step.
