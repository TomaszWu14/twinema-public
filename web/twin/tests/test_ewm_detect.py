"""„Wykryj z EWM”: propozycja szablonów, numeracji i wyjątków z kodów; round-trip = te same kody."""
from collections import defaultdict
from types import SimpleNamespace as NS

from django.test import SimpleTestCase

from twin.addressing import expand_model
from twin.ewm_detect import detect


def master_of(pairs):
    return [(code, typ, 0, 0) for code, typ in pairs]


def rows_of(n_bays):
    return [{"zone": "Z1", "rack_id": a, "n_bays": n} for a, n in n_bays.items()]


def expand_proposal(prop, n_bays, width_cm=280):
    """Propozycja → obiekty jak z bazy → rozwinięte kody per przejście."""
    tpl = {t["key"]: NS(pallets_per_beam=t["pallets_per_beam"], levels=t["levels"]) for t in prop["templates"]}
    triples = []
    for r in prop["rows"]:
        row = NS(zone=r["zone"], rack_id=r["rack_id"], n_bays=n_bays[r["rack_id"]], bay_width_cm=width_cm,
                 bay_numbers=r["bay_numbers"], reverse=False)
        ovs = [NS(template=tpl.get(o.get("template")), **{k: v for k, v in o.items() if k != "template"})
               for o in r["overrides"]]
        triples.append((row, tpl[r["template"]], ovs))
    locs, dups = expand_model(triples)
    by_aisle = defaultdict(set)
    for loc in locs:
        by_aisle[loc["aisle"]].add(loc["code"])
    return by_aisle, dups



class DetectIrregularBayTests(SimpleTestCase):
    def test_irregular_bay_gets_nearest_template_plus_skip_and_add(self):
        pairs = []
        for bay in (10, 11, 12):
            pairs += [(f"Z1-01-{bay}{p}{L}", "0010") for p in range(3) for L in "AB"]
        pairs += [("Z1-01-130A", "0010"), ("Z1-01-131A", "0010"), ("Z1-01-130P", "0010")]
        pairs += [(f"Z1-01-13{p}B", "0010") for p in range(3)]
        prop = detect(rows_of({"01": 4}), master_of(pairs))
        row = prop["rows"][0]
        self.assertEqual(len(prop["templates"]), 1)
        loc_ov = sorted((o["action"], o["bay"], o["position"], o["letter"]) for o in row["overrides"])
        self.assertEqual(loc_ov, [("add", 13, 0, "P"), ("skip", 13, 2, "A")])
        by_aisle, _ = expand_proposal(prop, {"01": 4})
        self.assertEqual(by_aisle["01"], {c for c, _ in pairs})


class DetectHeightsTests(SimpleTestCase):
    def test_level_heights_and_weights_are_medians_from_master(self):
        master = []
        for bay, (height, kg) in zip((10, 11, 12), ((1400, 900), (1500, 1000), (1600, 1100)), strict=True):
            master += [(f"Z1-01-{bay}{p}A", "0020", height, kg) for p in range(3)]
            master += [(f"Z1-01-{bay}{p}B", "0010", 0, 0) for p in range(3)]
        prop = detect(rows_of({"01": 3}), master)
        self.assertEqual(len(prop["templates"]), 1)
        levels = {lv["letter"]: lv for lv in prop["templates"][0]["levels"]}
        self.assertEqual((levels["A"]["height_mm"], levels["A"]["max_kg"]), (1500, 1000))
        self.assertEqual((levels["B"]["height_mm"], levels["B"]["max_kg"]), (1000, 0))   # brak danych → domyślne
