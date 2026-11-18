# pkOrientToMinRect

Rotates objects around Z so the long side of their minimum XY rectangle is parallel to X or Y.

| Option | Effect |
|---|---|
| `Axis=X|Y` | Target axis for the long side. |
| `Group=No` | Each object rotates around its own rectangle center. |
| `Group=Yes` | All objects rotate together around the common rectangle center. |

## Notes

The smallest rotation is used (never more than 90 degrees).
