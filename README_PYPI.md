# lunamint

Standalone SVG/PNG banknote generation helpers.

## Install

```bash
pip install lunamint
```

## Gradio UI + API (optional)

```bash
pip install lunamint[gradio]
python -m lunamint.app.gradio_app
```

Gradio will print a local URL. The same app exposes a JSON API endpoint:

```
POST /run/predict
Content-Type: application/json

{
    "data": [
        "Ling Treasury",
        10,
        "./portraits/portrait_ling.png",
        "灵国国库",
        "天圆地方",
        160.0,
        60.0,
        300.0,
        ""
    ]
}
```

Response includes paths for `front_png` and `back_png` plus metadata.

## Usage

```python
from lunamint import generate_banknote_pair_svgs_pngs

result = generate_banknote_pair_svgs_pngs(
    name="Ling Treasury",
    denom=10,
    portrait_path="./portraits/portrait_ling.png",
    output_dir="./out/10",
)

print(result["front_svg"], result["back_svg"])
```
