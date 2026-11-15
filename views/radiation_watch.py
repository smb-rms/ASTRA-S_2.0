from core import risk, ui


def render():
    ui.title("Radiation Watch", "Radiation exposure during the mission. Limits and classifications come only from Risk Diagnostics.")
    ui.section("Radiation Measurements", "The sensor column is labelled mSv; whether it is a dose rate or a cumulative dose is not defined yet.")
    ui.cards_row([{"key": "radiation_rate", "status": ["radiation"]}, "radiation_cum"], show_delta=True)
    ui.section("Exposure Trends")
    ui.trend("radiation_rate", 300)
    ui.trend("radiation_cum", 300)
    ui.section("Exposure Summary")
    ui.history_table(["radiation_rate", "radiation_cum"])
    r = risk.load()
    ui.section("Risk Assessment Result")
    if r is None:
        ui.empty("No Risk Diagnostics output found.")
    else:
        rows = r["df"][r["df"]["category"].astype(str).str.contains("Radiation", case=False, na=False)] if "category" in r["df"] else r["df"].iloc[0:0]
        ui.risk_cards(rows, r) if not rows.empty else ui.empty("No radiation assessment available.")
