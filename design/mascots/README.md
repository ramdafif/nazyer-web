# Owner-supplied mascot artwork

`booking-original.png` is the supplied `1001108296.png`; `not-found-original.png`
is `1001108298.png`. Their existing transparency and illustration are preserved.
The unused alternate `1001108297.png` is not shipped as a runtime asset.

Static WebP variants are prepared once using the existing Pillow dependency:
copy each original, thumbnail to 320 or 640 square with LANCZOS, then save WebP
with quality 88 and method 6. Original square aspect ratios remain unchanged.
Templates use `asset_url`, `srcset` and explicit dimensions. No image processing
runs while serving these illustrations.
