# Macierz śledzenia

**[BA]** · wymaganie → historyjka → test → PR. Aktualizowana przy odbiorze każdej funkcji.
Ścieżki testów względem `web/`. PR sprzed wprowadzenia macierzy: „historia” (zob. `git log`).

| Wymaganie | Historyjki | Testy | PR |
|---|---|---|---|
| FR-001 | WF-101–103 | `masterdata/tests/test_importers.py`, `test_dane.py` | historia |
| FR-002 | WF-104 | `masterdata/tests/test_master_data.py` | historia |
| FR-003 | WF-105 | `masterdata/tests/test_dane.py`, `core/tests/test_seed_demo.py` | historia |
| FR-004 | WF-201–203 | `twin/tests/test_ewm_tasks_parser.py`, `test_ewm_tasks_flow.py`, `test_ewm_tasks_refresh.py`, `test_ewm_views.py` | historia |
| FR-005 | WF-204–205 | `twin/tests/test_design_day.py`, `test_design_calibration.py`, `test_design_forecast.py`, `ml/tests/test_ml.py` | historia |
| FR-006 | WF-206 | `twin/tests/test_design_compare.py`, `test_design_sim.py` | historia |
| FR-007 | WF-301, WF-305 | `twin/tests/test_design_generator.py`, `test_model_geometry.py`, `test_model_edit.py`, `test_warehouse_model_paste.py` | historia |
| FR-008 | WF-302–304 | `twin/tests/test_layout.py`, `test_layout_views.py`, `test_layout_structure*.py`, `test_aisles.py`, `test_site*.py`, `js/layout_core.test.mjs` | historia |
| FR-009 | WF-306 | `twin/tests/test_ewm_detect.py`, `test_ewm_service.py`, `test_addressing.py`, `test_bay_template_*.py` | historia |
| FR-010 | WF-401–403 | `equipment/tests/test_equipment.py`, `test_import.py`, `twin/tests/test_layout_equipment.py` | historia |
| FR-011 | WF-404 | `scenario/tests/test_costs.py` | historia |
| FR-012 | WF-501–502 | `scenario/tests/test_views.py`, `test_inbound.py`, `test_outbound.py` | historia |
| FR-013 | WF-503–504 | `scenario/tests/test_sim.py`, `test_sim_views.py`, `test_fleet_catalog.py`, `test_k3_fleet.py`, `test_placement.py` | historia |
| FR-014 | WF-505–506 | `scenario/tests/test_play.py`, `test_r2.py`, `test_r3.py`, `js/day_timeline.test.mjs` | historia |
| FR-015 | WF-601–604 | `scenario/tests/test_showcase.py`, `test_public_link.py`, `js/showcase.test.mjs` | historia |
| FR-016 | WF-701–704 | `studio/tests/*` | historia |
| FR-017 | WF-801–802 | `core/tests/test_role_matrix.py`, `test_foundation.py` | historia |
| FR-018 | WF-803–805 | `core/tests/test_demo.py`, `test_seed_demo.py` | historia |
| FR-019 | US-001 | `equipment/tests/test_equipment.py::OwnModelAuthorizationTests`, `test_import.py::test_import_does_not_overwrite_other_users_model` | ten PR (#68) |
| FR-010 (komunikat) | US-002 | `equipment/tests/test_equipment.py::OwnModelAuthorizationTests::test_delete_message_reports_removed_fleet_groups` | ten PR (#68) |
| NFR-002 | US-003 | `render/tests/test_worker_url.py` | ten PR (#68) |
| NFR-010 | — | CI: `.github/workflows/security.yml` | ten PR (#68) |
| FR-020 | US-004 | `core/tests/test_deletion.py` | ten PR (#68) |
| FR-021 | US-019 | `core/tests/test_navigation.py::ViewerSeesOnlyAccessibleLinksTests` | ten PR (#68) |
| NFR-007 (blokada logowania) | US-006 | `core/tests/test_foundation.py::ClientIpTests` | ten PR (#68) |
| NFR-009 (ochrona danych, demo) | US-011 | `core/tests/test_demo.py::DemoExposureTests` | ten PR (#68) |
| FR-023 | US-012 | `twin/tests/test_ewm_tasks_parser.py::OperatorPseudonymTests`, `test_ewm_tasks_flow.py::OperatorLoginNotStoredTests` | ten PR (#68) |
| NFR-012 (obliczenia tylko dla Projektanta, Z-3) | — | `twin/tests/test_design_sim.py::ViewerDoesNotComputeTests`, `test_design_calibration.py::ViewerDoesNotCalibrateTests` | ten PR (#68) |
| NFR-002 (stanowisko renderujące) | US-015 | `render/tests/test_render.py::…::test_job_gives_up_after_max_attempts`, `studio/tests/test_render_montage.py::…::test_montage_gives_up_after_max_attempts` | ten PR (#68) |
| FR-017 (strony błędów) | US-020 | `core/tests/test_error_pages.py` | ten PR (#68) |
| FR-012 (formularze) | US-021 | `scenario/tests/test_views.py::…::test_invalid_form_keeps_typed_values_once` | ten PR (#68) |
| NFR-015 | US-023 | CI: job `coverage` w `.github/workflows/ci.yml` (próg 80%) | ten PR (#68) |
| NFR-010 (skany blokujące) | US-014, US-018 | `core/tests/test_csrf_forms.py`; CI: `.github/workflows/security.yml` | ten PR (#68) |
| FR-022 | US-008 | `core/tests/test_audit.py` | ten PR (#68) |
| NFR-011–014 | US-005, US-007, US-009 | — | planowane |
