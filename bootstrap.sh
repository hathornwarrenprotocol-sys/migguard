#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-ai-liquid-plant}"
mkdir -p "$ROOT"/{plant,agent,tests,scripts,docs}

cat > "$ROOT/README.md" << 'EOF'
# AI Liquid Plant
Warm direct-to-chip hall model. Not a patent.
python scripts/run_sites.py
python scripts/size_buffer.py
python scripts/commission.py --site nordic
EOF

cat > "$ROOT/requirements.txt" << 'EOF'
# stdlib only
EOF

cat > "$ROOT/plant/__init__.py" << 'EOF'
from .model import CommercialAILiquidPlant, heating_cop
from .sizer import buffer_liters, liquid_step_kw, pcm_mass_kg
EOF

cat > "$ROOT/plant/model.py" << 'EOF'
from __future__ import annotations

def heating_cop(t_source_c: float, t_sink_c: float, eta: float = 0.45,
                cop_min: float = 2.4, cop_max: float = 7.5) -> float:
    ts = t_source_c + 273.15
    th = t_sink_c + 273.15
    if th <= ts + 2.0:
        return cop_max
    return max(cop_min, min(cop_max, eta * th / (th - ts)))

class CommercialAILiquidPlant:
    def __init__(self, name: str, rack_power_kw: float = 120.0, load_factor: float = 0.80,
                 liquid_capture_fraction: float = 0.80, heat_fraction: float = 0.96):
        self.name = name
        self.rack_power_kw = rack_power_kw
        self.load_factor = load_factor
        self.avg_it_kw = rack_power_kw * load_factor
        self.avg_total_heat_kw = self.avg_it_kw * heat_fraction
        self.avg_liquid_heat_kw = self.avg_total_heat_kw * liquid_capture_fraction
        self.avg_air_heat_kw = self.avg_total_heat_kw * (1.0 - liquid_capture_fraction)

    def evaluate_annual_dispatch(self, bins, has_district_offtaker=False, offtaker_fraction=0.70,
                                 dh_supply_c=75.0, t_source_c=47.0, fws_supply_c=37.0):
        cooling_kwh = heat_kwh = water_gal = 0.0
        pump = self.avg_it_kw * 0.012
        for b in bins:
            hours, db, wb = b["hours"], b["dry_bulb_c"], b["wet_bulb_c"]
            e, water, sold = pump, 0.0, 0.0
            if has_district_offtaker and b.get("offtaker_active", True):
                cop = heating_cop(t_source_c, dh_supply_c)
                q_hp = self.avg_liquid_heat_kw * offtaker_fraction
                q_dry = self.avg_liquid_heat_kw - q_hp
                w = q_hp / (cop - 1.0)
                sold = q_hp + w
                e += w + q_dry * 0.02
            else:
                if db <= (fws_supply_c - 5.0):
                    e += self.avg_liquid_heat_kw * 0.02
                else:
                    e += self.avg_liquid_heat_kw * 0.03
                    water += self.avg_liquid_heat_kw * 0.18
            if wb > 24.0:
                e += self.avg_air_heat_kw / 4.0
                water += self.avg_air_heat_kw * 0.25
            else:
                e += self.avg_air_heat_kw * 0.04
            cooling_kwh += e * hours
            heat_kwh += sold * hours
            water_gal += water * hours
        hours_y = sum(b["hours"] for b in bins) or 8760.0
        return {
            "site": self.name,
            "avg_it_kw": self.avg_it_kw,
            "q_liquid_kw": self.avg_liquid_heat_kw,
            "q_air_kw": self.avg_air_heat_kw,
            "annual_heat_kwh_th": heat_kwh,
            "annual_cooling_kwh": cooling_kwh,
            "annual_water_gal": water_gal,
            "cooling_pue": 1.0 + (cooling_kwh / hours_y) / self.avg_it_kw,
        }

    def incremental_value(self, dispatch, elec_rate, heat_rate, water_per_kgal=8.0,
                          capex_this=36000.0, capex_alt=28000.0,
                          alt_pue_adder=0.18, alt_gal_per_kwh=1.2):
        alt_e = self.avg_it_kw * alt_pue_adder * 8760.0
        alt_w = self.avg_it_kw * alt_gal_per_kwh * 8760.0
        e_save = (alt_e - dispatch["annual_cooling_kwh"]) * elec_rate
        w_save = ((alt_w - dispatch["annual_water_gal"]) / 1000.0) * water_per_kgal
        heat = dispatch["annual_heat_kwh_th"] * heat_rate
        nov = e_save + w_save + heat
        dcap = capex_this - capex_alt
        payback = None if nov <= 0 else max(dcap, 0.0) / nov
        return {"heat_rev": heat, "elec_save": e_save, "water_save": w_save,
                "nov": nov, "delta_capex": dcap, "payback_yr": payback}
EOF

cat > "$ROOT/plant/sizer.py" << 'EOF'
def liquid_step_kw(rack_kw=120.0, idle_frac=0.20, full_frac=1.0, heat_frac=0.96, liquid_frac=0.80):
    return rack_kw * (full_frac - idle_frac) * heat_frac * liquid_frac

def buffer_liters(q_step_kw, lag_s=10.0, dt_k=1.5, cp=3.8, rho=1040.0, mix=0.85):
    return (q_step_kw * lag_s) / (cp * dt_k * rho * mix) * 1000.0

def pcm_mass_kg(q_step_kw, lag_s=10.0, h_fus=180.0, utilization=0.40):
    return (q_step_kw * lag_s) / (h_fus * utilization)
EOF

cat > "$ROOT/plant/sites.py" << 'EOF'
SITES = [
    {"name":"Nordic+DH","load_factor":0.80,"offtaker":True,"dh_c":70.0,"elec":0.11,"heat":0.035,
     "capex_this":42000,"capex_alt":28000,"alt_adder":0.16,"alt_w":0.8,
     "bins":[
        {"hours":4000,"dry_bulb_c":-5,"wet_bulb_c":-7,"offtaker_active":True},
        {"hours":3760,"dry_bulb_c":10,"wet_bulb_c":7,"offtaker_active":True},
        {"hours":1000,"dry_bulb_c":22,"wet_bulb_c":15,"offtaker_active":False}]},
    {"name":"EU+DH","load_factor":0.75,"offtaker":True,"dh_c":80.0,"elec":0.18,"heat":0.040,
     "capex_this":45000,"capex_alt":30000,"alt_adder":0.16,"alt_w":0.8,
     "bins":[
        {"hours":3000,"dry_bulb_c":3,"wet_bulb_c":1,"offtaker_active":True},
        {"hours":4200,"dry_bulb_c":15,"wet_bulb_c":11,"offtaker_active":True},
        {"hours":1560,"dry_bulb_c":30,"wet_bulb_c":20,"offtaker_active":False}]},
    {"name":"Midwest","load_factor":0.85,"offtaker":False,"dh_c":75.0,"elec":0.09,"heat":0.0,
     "capex_this":32000,"capex_alt":26000,"alt_adder":0.18,"alt_w":1.2,
     "bins":[
        {"hours":3000,"dry_bulb_c":-2,"wet_bulb_c":-4,"offtaker_active":False},
        {"hours":4200,"dry_bulb_c":16,"wet_bulb_c":11,"offtaker_active":False},
        {"hours":1560,"dry_bulb_c":32,"wet_bulb_c":23,"offtaker_active":False}]},
    {"name":"Desert","load_factor":0.80,"offtaker":False,"dh_c":75.0,"elec":0.13,"heat":0.0,
     "capex_this":36000,"capex_alt":30000,"alt_adder":0.22,"alt_w":1.6,
     "bins":[
        {"hours":2000,"dry_bulb_c":12,"wet_bulb_c":6,"offtaker_active":False},
        {"hours":4500,"dry_bulb_c":28,"wet_bulb_c":15,"offtaker_active":False},
        {"hours":2260,"dry_bulb_c":43,"wet_bulb_c":22,"offtaker_active":False}]},
    {"name":"Singapore","load_factor":0.80,"offtaker":False,"dh_c":75.0,"elec":0.20,"heat":0.0,
     "capex_this":38000,"capex_alt":32000,"alt_adder":0.24,"alt_w":1.4,
     "bins":[
        {"hours":2800,"dry_bulb_c":27,"wet_bulb_c":24,"offtaker_active":False},
        {"hours":4500,"dry_bulb_c":31,"wet_bulb_c":26,"offtaker_active":False},
        {"hours":1460,"dry_bulb_c":35,"wet_bulb_c":28,"offtaker_active":False}]},
]
EOF

cat > "$ROOT/agent/__init__.py" << 'EOF'
EOF

cat > "$ROOT/agent/pid_checklist.py" << 'EOF'
CHECKLIST = [
    "TCS isolated from FWS at liquid-to-liquid CDU",
    "Fast valves on FWS RETURN (hot), fail-to-dry-cooler",
    "DPRV across heat-pump evaporator",
    "Buffer on FWS return, sized for load step * compressor lag",
    "DH flow/pressure trip is hardwired",
    "On trip: cooler path + FWS pumps/fans; TCS boost does not reject yard heat",
    "If FWS supply still rising at 5-8 s: rack power cap",
    "No outdoor dry-bulb as the trip interlock",
    "Air remainder has RDHX or CRAH",
    "No generator / MHD / on-die sCO2 on the critical path",
]
def render():
    return "\n".join(f"[ ] {x}" for x in CHECKLIST)
EOF

cat > "$ROOT/agent/commission.py" << 'EOF'
from plant.model import CommercialAILiquidPlant
from plant.sizer import buffer_liters, liquid_step_kw
from plant.sites import SITES
from agent.pid_checklist import render as checklist

def commission(site_name: str) -> str:
    cfg = next(s for s in SITES if s["name"].lower().startswith(site_name.lower()))
    plant = CommercialAILiquidPlant(cfg["name"], load_factor=cfg["load_factor"])
    d = plant.evaluate_annual_dispatch(cfg["bins"], cfg["offtaker"], dh_supply_c=cfg["dh_c"])
    v = plant.incremental_value(d, cfg["elec"], cfg["heat"], capex_this=cfg["capex_this"],
                                capex_alt=cfg["capex_alt"], alt_pue_adder=cfg["alt_adder"],
                                alt_gal_per_kwh=cfg["alt_w"])
    liters = buffer_liters(liquid_step_kw())
    pb = "n/a" if v["payback_yr"] is None else f"{v['payback_yr']:.1f}"
    return "\n".join([
        f"SITE {cfg['name']}",
        f"  avg IT            {plant.avg_it_kw:.1f} kW",
        f"  liquid / air      {d['q_liquid_kw']:.1f} / {d['q_air_kw']:.1f} kW",
        f"  cooling PUE       {d['cooling_pue']:.3f}",
        f"  heat sold         {d['annual_heat_kwh_th']/1000:.0f} MWh_th",
        f"  cooling electric  {d['annual_cooling_kwh']/1000:.0f} MWh",
        f"  water             {d['annual_water_gal']/1000:.0f} kgal",
        f"  NOV               ${v['nov']:,.0f}/yr",
        f"  delta capex       ${v['delta_capex']:,.0f}",
        f"  simple payback    {pb} yr",
        f"  offtaker          {'YES' if cfg['offtaker'] else 'NO — skip HP'}",
        f"  buffer 20-100%    {liters:.0f} L PG25 @ 10s / 1.5K",
        "", "P&ID CHECK", checklist(),
        "", "HIL if you want IP: 20->100% step and DH trip. Then a lawyer.",
    ])
EOF

cat > "$ROOT/scripts/run_sites.py" << 'EOF'
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plant.model import CommercialAILiquidPlant
from plant.sites import SITES
print(f"{'site':<12} {'LF':>4} {'PUE_c':>6} {'heat MWh':>9} {'e MWh':>7} {'NOV$':>8} {'yr':>6}")
for cfg in SITES:
    p = CommercialAILiquidPlant(cfg["name"], load_factor=cfg["load_factor"])
    d = p.evaluate_annual_dispatch(cfg["bins"], cfg["offtaker"], dh_supply_c=cfg["dh_c"])
    v = p.incremental_value(d, cfg["elec"], cfg["heat"], capex_this=cfg["capex_this"],
                            capex_alt=cfg["capex_alt"], alt_pue_adder=cfg["alt_adder"],
                            alt_gal_per_kwh=cfg["alt_w"])
    pb = "n/a" if v["payback_yr"] is None else f"{v['payback_yr']:.1f}"
    print(f"{cfg['name']:<12} {cfg['load_factor']:4.2f} {d['cooling_pue']:6.3f} "
          f"{d['annual_heat_kwh_th']/1000:9.0f} {d['annual_cooling_kwh']/1000:7.0f} "
          f"{v['nov']:8.0f} {pb:>6}")
EOF

cat > "$ROOT/scripts/size_buffer.py" << 'EOF'
#!/usr/bin/env python3
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plant.sizer import buffer_liters, liquid_step_kw, pcm_mass_kg
ap = argparse.ArgumentParser()
ap.add_argument("--step-kw", type=float, default=None)
ap.add_argument("--lag-s", type=float, default=10.0)
ap.add_argument("--dt-k", type=float, default=1.5)
a = ap.parse_args()
step = a.step_kw if a.step_kw is not None else liquid_step_kw()
print(f"liquid step     {step:.2f} kW")
print(f"PG25 buffer     {buffer_liters(step, a.lag_s, a.dt_k):.0f} L")
print(f"PCM mass ~      {pcm_mass_kg(step, a.lag_s):.1f} kg (40% used)")
EOF

cat > "$ROOT/scripts/commission.py" << 'EOF'
#!/usr/bin/env python3
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.commission import commission
ap = argparse.ArgumentParser()
ap.add_argument("--site", default="nordic")
print(commission(ap.parse_args().site))
EOF

cat > "$ROOT/tests/test_sizer.py" << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plant.sizer import buffer_liters, liquid_step_kw
def test_step_is_about_74kw():
    q = liquid_step_kw()
    assert 70.0 < q < 78.0
def test_buffer_near_150l():
    v = buffer_liters(liquid_step_kw(), 10.0, 1.5)
    assert 130.0 < v < 170.0
if __name__ == "__main__":
    test_step_is_about_74kw()
    test_buffer_near_150l()
    print("ok")
EOF

cat > "$ROOT/docs/skid.md" << 'EOF'
TCS 40/50 C -> CDU -> FWS return ~47 C -> 150 L buffer -> fail-to-cooler and/or HP.
Trip on DH loss. Fans/pumps on FWS. Power cap if supply still rising.
Tests: 20-100% step, DH trip.
EOF

echo "created $ROOT"
