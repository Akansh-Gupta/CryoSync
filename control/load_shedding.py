"""
Load Shedding Controller
----------------------------
Decides, hour by hour, whether Low/Medium priority equipment should be shed
(turned off) based on a trigger metric (e.g. wind speed as a storm proxy).

Three timing rules prevent rapid on/off flickering:
  1. confirm_hours       -> trigger must hold for N hours before shedding starts
  2. min_shed_duration_hours -> once shed, stays off for at least N hours
  3. release_threshold (hysteresis) -> restore point is LOWER than the trigger
     point, so hovering near one value doesn't cause flapping
  4. cooldown_hours      -> after restoring, must wait N hours before it can
     shed again (protects against back-to-back cycling around a noisy signal)
"""
import numpy as np


def simulate_load_shedding(trigger_values, shed_cfg):
    n = len(trigger_values)
    shed_active = np.zeros(n, dtype=bool)

    state = "on"          # "on" = normal operation, "off" = shed
    confirm_count = 0      # consecutive hours trigger condition has held
    hours_in_state = 0     # hours spent in current state
    cooldown_remaining = 0

    events = []  # (start_idx, end_idx) of each shed event, for reporting
    shed_start = None

    for i in range(n):
        v = trigger_values[i]

        if state == "on":
            hours_in_state += 1
            if cooldown_remaining > 0:
                cooldown_remaining -= 1

            if v >= shed_cfg["trigger_threshold"] and cooldown_remaining == 0:
                confirm_count += 1
            else:
                confirm_count = 0

            if confirm_count >= shed_cfg["confirm_hours"]:
                state = "off"
                hours_in_state = 0
                confirm_count = 0
                shed_start = i

        else:  # state == "off"
            hours_in_state += 1
            can_restore = (hours_in_state >= shed_cfg["min_shed_duration_hours"]
                            and v <= shed_cfg["release_threshold"])
            if can_restore:
                state = "on"
                hours_in_state = 0
                cooldown_remaining = shed_cfg["cooldown_hours"]
                events.append((shed_start, i))

        shed_active[i] = (state == "off")

    if state == "off" and shed_start is not None:
        events.append((shed_start, n - 1))

    return shed_active, events


def apply_shedding(total_load_kw, shed_kw_available, shed_active):
    """Subtract the shed-eligible load during active shed hours."""
    adjusted = total_load_kw.copy()
    adjusted[shed_active] -= shed_kw_available[shed_active]
    return np.clip(adjusted, 0, None)


def summarize_events(events, timestamps):
    if not events:
        return "No shedding events triggered."
    durations = [(e - s + 1) for s, e in events]
    lines = [f"{len(events)} shedding event(s), avg duration {np.mean(durations):.1f} hours, "
             f"longest {max(durations)} hours, total {sum(durations)} shed-hours"]
    for s, e in events[:10]:
        lines.append(f"  {timestamps.iloc[s]}  ->  {timestamps.iloc[e]}  ({e - s + 1}h)")
    if len(events) > 10:
        lines.append(f"  ... and {len(events) - 10} more")
    return "\n".join(lines)
