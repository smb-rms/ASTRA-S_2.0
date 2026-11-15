from core import risk, ui


def render():
    ui.title("Cabin Environment", "Conditions inside the spacecraft that may affect health and mission safety.")
    ui.section("Current Environmental Conditions")
    ui.cards_row([{"key": "oxygen", "status": ["cabin_o2"]}, {"key": "cabin_temp", "status": ["cabin_temp"]},
                  {"key": "cabin_co2", "status": ["co2"]}], show_delta=True)
    ui.section("Environmental Trends")
    ui.trend_grid(["oxygen", "cabin_temp", "cabin_co2"], per_row=3, height=300)
    ui.section("Environmental History")
    ui.history_table(["oxygen", "cabin_temp", "cabin_co2"])
    r = risk.load()
    ui.section("Related Alerts")
    ui.alert_cards(risk.related(r, ["environment"]), r) if r else ui.empty("No Risk Diagnostics output found.")
