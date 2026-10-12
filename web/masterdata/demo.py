"""Dane demonstracyjne (syntetyczne): materiały zgodne z `tools/ewm_demo_tasks.py` i stan
magazynu rozłożony po regałach wybranego modelu hali — żeby scena 3D miała palety, a dzień
projektowy grupy towarowe, bez żadnych prawdziwych danych."""
import random
from datetime import date, timedelta

from twin.addressing import make_code

GROUPS = ["Elektronika", "AGD", "Chemia gospodarcza", "Spożywcze suche", "Tekstylia",
          "Zabawki", "Narzędzia", "Opakowania"]
LEVEL_LETTERS = "ABCDE"              # poziomy 1–5 od podłogi (twin/ewm_levels.py)
N_MATERIALS = 3000                   # = materiały w tools/ewm_demo_tasks.py
PALLET_SLOT_M = 0.9                  # szerokość miejsca na paletę EU wzdłuż belki


def material_codes(n=N_MATERIALS):
    return [f"1{i:07d}" for i in range(n)]


# Udział materiałów w strefach specjalnych (syntetyczny): ADR głównie chemia, gabaryty — narzędzia/AGD.
FLAG_SHARE = {"temp_controlled": ("Spożywcze suche", 0.15), "adr": ("Chemia gospodarcza", 0.25),
              "oversize": ("Narzędzia", 0.10), "high_value": ("Elektronika", 0.15)}


def demo_materials(n=N_MATERIALS, seed=7):
    """Wiersze materiałów (dicty pól Material) z losowymi, ale wiarygodnymi wymiarami:
    sztuka → karton (pcs sztuk mieści się objętościowo) → paleta EUR (warstwy do ~1,5 m)."""
    rng = random.Random(seed)
    out = []
    for i, code in enumerate(material_codes(n)):
        group = GROUPS[i % len(GROUPS)]
        l, w, h = rng.choice([(60, 40, 40), (40, 30, 30), (30, 20, 20), (60, 40, 20), (80, 60, 50)])
        pcs = rng.choice([1, 2, 4, 6, 12, 24, 48])
        layer = (120 // l) * (80 // w) or 1
        layers = max(1, int(150 // h))
        kg = round(min(rng.uniform(2, 18), 900 / (layer * layers)), 1)   # paleta ≤ ~900 kg na EUR
        k = (0.85 / pcs) ** (1 / 3)                     # sztuka ≈ 85 % kartonu / pcs (objętościowo)
        row = {"code": code, "name": f"{group} — artykuł {i + 1:04d}", "group": group, "unit": "SZT",
               "piece_l_cm": round(l * k, 1), "piece_w_cm": round(w * k, 1), "piece_h_cm": round(h * k, 1),
               "piece_kg": round(kg * 0.95 / pcs, 3), "pcs_per_carton": pcs,
               "carton_l_cm": l, "carton_w_cm": w, "carton_h_cm": h, "carton_kg": kg,
               "cartons_per_layer": layer, "layers_per_pallet": layers, "cartons_per_pallet": layer * layers,
               "pallet_h_cm": round(layers * h + 14, 1), "abc_manual": ""}
        for flag, (grp, share) in FLAG_SHARE.items():
            row[flag] = group == grp and rng.random() < share
        out.append(row)
    return out


def demo_stock(racks, fill=0.7, seed=11, materials=None, today=None):
    """Pozycje stanu dla regałów modelu: ~`fill` miejsc zajętych, materiały wg rotacji (Pareto),
    jedna paleta na miejsce. `racks` = dicty z `twin.blender_scene.model_racks`."""
    rng = random.Random(seed)
    materials = materials or material_codes()
    weights = [1 / (i + 1) ** 0.9 for i in range(len(materials))]
    today = today or date.today()
    out, n = [], 0
    for r in racks:
        # Palety na belce z szerokości gniazda (EU 0,8 m + luz ~0,1 m), cyfra pozycji w kodzie: 0–9.
        # round, nie // — 2,7 // 0,9 = 2,0 w liczbach zmiennoprzecinkowych; ta sama reguła co design_kpi.rack_to_element
        per_bay = min(9, max(1, round(r["width"] / max(1, r["n_bays"]) / PALLET_SLOT_M)))
        for bay in range(r["n_bays"]):
            for pos in range(per_bay):
                for level in range(1, min(r["n_levels"], len(LEVEL_LETTERS)) + 1):
                    if rng.random() > fill:
                        continue
                    n += 1
                    mat = rng.choices(materials, weights)[0]
                    code = make_code(r["zone"], r["rack_id"], 10 + bay, pos, LEVEL_LETTERS[level - 1])
                    out.append({"location_code": code, "material_code": mat,
                                "qty": rng.randrange(8, 60), "unit": "KAR",
                                "hu": f"HU{n:08d}", "lot": f"L{rng.randrange(10**5):05d}",
                                "expiry": (today + timedelta(days=rng.randrange(30, 720))
                                           if rng.random() < 0.4 else None)})
    return out
