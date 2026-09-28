"""
Step 2: Equipment & Load Library
---------------------------------
Representative electrical systems defined BY FUNCTION, not as an attempt
to reproduce any specific real station's exact inventory.

Each system stores:
  zone, nominal_power_kw, priority, min_power_kw, behavior

behavior controls how the equipment operating model (Step 5) drives it:
  "continuous"      -> always on near nominal (critical loads)
  "occupancy_driven" -> scales with occupancy/activity
  "thermal_driven"   -> scales inversely with outdoor temperature
  "schedule_driven"  -> follows a daily time-of-day pattern
  "research_driven"  -> scales with research activity level
"""

EQUIPMENT_LIBRARY = [
    # ---------------- Critical Infrastructure ----------------
    {"id": "crit_heating", "zone": "critical", "name": "Essential heating",
     "nominal_power_kw": 18.0, "min_power_kw": 10.0, "priority": "Critical",
     "behavior": "thermal_driven"},
    {"id": "crit_comms", "zone": "critical", "name": "Communication systems",
     "nominal_power_kw": 4.0, "min_power_kw": 3.5, "priority": "Critical",
     "behavior": "continuous"},
    {"id": "crit_servers", "zone": "critical", "name": "Servers / data systems",
     "nominal_power_kw": 5.0, "min_power_kw": 4.5, "priority": "Critical",
     "behavior": "continuous"},
    {"id": "crit_water", "zone": "critical", "name": "Water treatment / desalination",
     "nominal_power_kw": 6.0, "min_power_kw": 3.0, "priority": "Critical",
     "behavior": "occupancy_driven"},
    {"id": "crit_emergency", "zone": "critical", "name": "Emergency systems",
     "nominal_power_kw": 2.0, "min_power_kw": 1.8, "priority": "Critical",
     "behavior": "continuous"},

    # ---------------- Residential ----------------
    {"id": "res_heating", "zone": "residential", "name": "Residential heating",
     "nominal_power_kw": 22.0, "min_power_kw": 6.0, "priority": "High",
     "behavior": "thermal_driven"},
    {"id": "res_lighting", "zone": "residential", "name": "Lighting",
     "nominal_power_kw": 5.0, "min_power_kw": 0.5, "priority": "Medium",
     "behavior": "schedule_driven"},
    {"id": "res_kitchen", "zone": "residential", "name": "Kitchen equipment",
     "nominal_power_kw": 9.0, "min_power_kw": 0.5, "priority": "High",
     "behavior": "schedule_driven"},
    {"id": "res_refrigeration", "zone": "residential", "name": "Refrigeration",
     "nominal_power_kw": 4.0, "min_power_kw": 2.5, "priority": "High",
     "behavior": "continuous"},
    {"id": "res_laundry", "zone": "residential", "name": "Laundry",
     "nominal_power_kw": 6.0, "min_power_kw": 0.0, "priority": "Low",
     "behavior": "occupancy_driven"},
    {"id": "res_general", "zone": "residential", "name": "General appliances",
     "nominal_power_kw": 7.0, "min_power_kw": 1.0, "priority": "Medium",
     "behavior": "occupancy_driven"},

    # ---------------- Research ----------------
    {"id": "res_lab_equip", "zone": "research", "name": "Laboratory equipment",
     "nominal_power_kw": 10.0, "min_power_kw": 2.0, "priority": "High",
     "behavior": "research_driven"},
    {"id": "res_computers", "zone": "research", "name": "Research computing",
     "nominal_power_kw": 6.0, "min_power_kw": 2.0, "priority": "Medium",
     "behavior": "research_driven"},
    {"id": "res_freezers", "zone": "research", "name": "Sample freezers",
     "nominal_power_kw": 5.0, "min_power_kw": 4.0, "priority": "High",
     "behavior": "continuous"},
    {"id": "res_instruments", "zone": "research", "name": "Scientific instruments",
     "nominal_power_kw": 7.0, "min_power_kw": 1.5, "priority": "Medium",
     "behavior": "research_driven"},
    {"id": "res_workshop", "zone": "research", "name": "Workshop / fabrication",
     "nominal_power_kw": 8.0, "min_power_kw": 0.0, "priority": "Low",
     "behavior": "schedule_driven"},
]


def total_nominal_by_zone():
    totals = {}
    for eq in EQUIPMENT_LIBRARY:
        totals[eq["zone"]] = totals.get(eq["zone"], 0.0) + eq["nominal_power_kw"]
    return totals


if __name__ == "__main__":
    for zone, total in total_nominal_by_zone().items():
        print(f"{zone}: {total:.1f} kW nominal")
