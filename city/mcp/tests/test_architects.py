"""The architects: rounds produce valid, ranked, novel candidates; adoption writes the kit and drifts taste."""

import json
import shutil
from pathlib import Path

from voxkit.architects import FEATURES, Studio, features, mutate, novelty
from voxkit.grammar import validate

KIT = Path(__file__).resolve().parents[2] / "kit"


def _studio(tmp_path: Path) -> Studio:
    kit = tmp_path / "kit"
    kit.mkdir()
    for p in KIT.glob("*.json"):
        shutil.copy(p, kit / p.name)
    return Studio(tmp_path / "agents", kit, seed=7)


def test_mutations_stay_valid_often_enough(tmp_path: Path) -> None:
    st = _studio(tmp_path)
    kit = st.kit()
    base = kit["u1"]
    ok = 0
    for _ in range(40):
        cand = mutate(base, st.rng, list(kit.values()), strength=4)
        spec, errors, _ = validate(cand)
        ok += spec is not None and not errors
    assert ok >= 30, f"only {ok}/40 mutations validated"


def test_round_ranks_candidates_and_adoption_drifts(tmp_path: Path) -> None:
    st = _studio(tmp_path)
    before = {a.id: dict(a.taste) for a in st.architects}
    rec = st.run_round({"text": "a tower for the Quant Desk", "neighbours": ["t1", "u3"]})
    cands = rec["candidates"]
    assert len(cands) >= 3
    assert cands == sorted(cands, key=lambda c: -c["score"])
    for c in cands:
        assert c["novelty"] > 0.02, "a candidate should not be a copy of the kit"
        assert c["spec"]["architect"] in before
        assert c["spec"]["lineage"]
    res = st.adopt(rec["id"], cands[0]["id"])
    assert (tmp_path / "kit" / f"{res['kit_id']}.json").exists()
    st2 = Studio(tmp_path / "agents", tmp_path / "kit")  # reload from disk
    after = {a.id: a.taste for a in st2.architects}
    moved = sum(1 for a in before for k in FEATURES if abs(before[a][k] - after[a][k]) > 1e-6)
    assert moved > 0, "taste should drift after adoption"
    winner = next(a for a in st2.architects if a.id == cands[0]["architect"])
    assert winner.wins == 1 and res["kit_id"] in winner.history
    rec2 = json.loads((tmp_path / "agents" / "rounds" / f"{rec['id']}.json").read_text())
    assert rec2["adopted"][0]["kit_id"] == res["kit_id"]


def test_novelty_is_zero_for_a_copy(tmp_path: Path) -> None:
    st = _studio(tmp_path)
    specs = [s for s in (validate(v)[0] for v in st.kit().values()) if s is not None]
    assert novelty(specs[0], specs) < 1e-9
    f = features(specs[0])
    assert set(f) == set(FEATURES) and all(0 <= v <= 1 for v in f.values())
