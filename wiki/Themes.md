# Themes

Everything here is in **Settings → Appearance**, and changes apply right away.

## Glass themes

- **Themes:** Default, Cool Glass, Warm Glass, Lilac and Heart Glass, in light and dark (Lilac is light only).
- **Glass effects:** Efficient (the default), Full or Off, and a simpler look while training if you want it.
- Pick the font, and **Save as theme** keeps your mix.

## CSS themes

Drag a `.css` file anywhere onto **Settings → Appearance** (or click the drop zone to choose one), and it's installed and switched on. It's saved in LoRA Studio's data folder, so updates never touch it, and it's included in backups. Switch between your CSS themes, turn them off or delete them in the same card. Picking one of the built-in themes turns the CSS theme off.

A CSS theme can set these values for the whole app:

- **Corners:** `--r-xs` (tiny bits like checkboxes), `--r-sm`, `--r-md`, `--r-lg`, `--r-xl` and `--pill`. Set them all to `0` for square corners everywhere. Circles, like switch knobs, stay round.
- **Corner shape:** `--corner-shape` is `round` by default. Set it to `bevel` for cut corners, or `notch`, `scoop`, `squircle` or `superellipse(…)`. Borders, shadows and focus rings follow the shape, and circles stay round. It works in the Windows app and in Chrome or Edge. Firefox, Safari and most Linux setups keep rounded corners for now.

## Your own styles

`web/css/custom.css` is loaded last, so anything you put there wins, even over a CSS theme. It has a few examples to start from, and updates never touch it.
