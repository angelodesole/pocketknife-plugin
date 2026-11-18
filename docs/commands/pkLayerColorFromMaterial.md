# pkLayerColorFromMaterial

Sets each layer color to the diffuse color of the layer material (Base Color for PBR materials).

| Option | Effect |
|---|---|
| `Mode=Default` | Only the layer color changes, so only ByLayer objects change color. |
| `Mode=Override` | Also resets every object on those layers (hidden and locked included) to ByLayer. |
| `AllLayers=No` | Acts on the layers of the selected objects. |
| `AllLayers=Yes` | Press Enter to act on every layer. |

## Notes

Layers without a material are skipped and listed on the command line.
