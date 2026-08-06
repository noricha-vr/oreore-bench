import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hy3_model_card_links_to_t512_branch() -> None:
    script = """
global.window = {};
require('./public/data.js');
const model = window.MODELS['hy3-t512'];
const link = model.links.find(({ label }) => label === 'avlp12 MLX版');
console.log(JSON.stringify(link));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == {
        "label": "avlp12 MLX版",
        "href": "https://huggingface.co/avlp12/Hy3-Alis-MLX-Dynamic/tree/T512",
    }
