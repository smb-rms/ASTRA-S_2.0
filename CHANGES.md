# Changes in this update

| Page / area | File and place | What changed |
|---|---|---|
| Crew Profile - photo upload | views/crew_profile.py, `_photo_uploader()` and `render()` | An "Upload profile picture" box now sits under each astronaut's photo. The file is saved to images/astronaut_N.png (N = 1, 2, 3). |
| Crew Profile - baseline | views/crew_profile.py, `_profile_files()`, `_astronauts()`, `_group_of()`, `_baseline_rows()` | Reads crew_profile.csv and astronaut_profiles_and_baselines.csv together, matched by astronaut_id. Fields with "baseline" in the name go to Baseline; mean and SD columns are shown as "57.97 ± 2 bpm". |
| Vitals & Activity | views/vitals_activity.py, end of `render()` | Removed the "3D Anatomy Reference" section and its import. |
| Crew Wellbeing | core/sensor_diagnostics.py, `mood_table()` | Timestamps are parsed file by file. Before, the survey rows (format 2026-11-15 03:07) were dropped when merged with the mood logs (2026-11-01 20:00:00), so Confinement and Discomfort had no data. |
| Nutrition Log | views/nutrition_log.py, `_food_db()`, `_history()`; core/sensor_diagnostics.py, `food_tables()` | The Meal Database is built from the dishes in all three food logs. History shows every astronaut with an Astronaut filter. |
| Risk Assessment | views/risk_assessment.py | Removed the "Sleep monitoring report". The correlation expander now only holds the Spearman matrix. "Important data limitations" is kept. |
| Wrong data fix | core/data.py, `resolve()` | Profile/baseline files and *_baseline_* / *_status columns are never used as measurements. |
| Wrong data fix | core/data.py, `_read_all()` | The text "None" (allergies: None) is kept as text instead of becoming empty. |
| Radiation Watch | core/ui.py, `history_table()` | The history table no longer fails when two measurements use different time axes. |
| Crew Profile | views/crew_profile.py, end of `render()` | Removed the "How the profile files were read" expander. |
| Sleep quality 100% | core/sleep_diagnostics.py `quality_basis()`, views/sleep.py under the summary cards | A note now says which parts the quality score used. Duration only (no efficiency, WASO or fragmentation columns) means a full night scores 100%. |
| Numbers changing | core/data.py `resolve()`, `sleep_source()`, `_read_all()` | The file used for each measurement no longer depends on file dates. Rule: single-astronaut files first, then the file with the most readings, then the lowest astronaut id, then file name. Sleep cards all come from the same sleep file. A sleep file holding several astronauts is cut to its first astronaut. |
