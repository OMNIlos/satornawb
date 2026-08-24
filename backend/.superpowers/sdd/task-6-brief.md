### Task 6: Final Verification

**Files:**
- No planned file modifications.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified backend and frontend behavior.

- [ ] **Step 1: Run focused backend tests**

Run from `D:\ogni-elfs`:

```powershell
pytest -q tests/test_report_data_mart.py tests/test_report_materialization_from_data_mart.py tests/test_report_prewarm.py tests/test_wb_reports_bff.py tests/test_sprint_d_reports.py tests/test_rnp_runtime.py
```

Expected: PASS.

- [ ] **Step 2: Run frontend report tests and typecheck**

Run from `D:\ogni-frontend\frontend`:

```powershell
npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts src/features/vella-parity/weekLiveSource.test.ts src/features/wb-reports/repository.test.ts
npx tsc -b --noEmit
```

Expected: PASS.

- [ ] **Step 3: Inspect git status in both repos**

Run:

```powershell
Set-Location D:\ogni-elfs
git status --short
Set-Location D:\ogni-frontend
git status --short
```

Expected: no uncommitted files except files intentionally left for review.

- [ ] **Step 4: Verify no direct WB runtime fallback remains in report materializers**

Run from `D:\ogni-elfs`:

```powershell
rg -n "refresh_wb_data_sources|build_wb_reports_sources_snapshot|build_ads_attribution_snapshot|WBClient|Wildberries" app\repricer_tasks.py app\routers\wb_reports_bff.py app\report_prewarm.py
```

Expected: no hits inside report materialization paths for `stock`, `ads`, `rnp`, `abc`, `pnl`, `expenses`, or `week-over-week`; hits are allowed only in WB sync and prewarm orchestration paths.
