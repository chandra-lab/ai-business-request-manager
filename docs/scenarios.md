# Mandatory test scenarios (1–6)

Canonical inputs live in `backend/app/ai/fixtures.py` → `scenario_sample_inputs()`.
Automated coverage: `backend/tests/test_scenarios.py`.

Threshold defaults: auto-assign ≥ **0.85**; review band **0.60–0.84**; clarification **&lt; 0.60**.

| ID | Topic | Expected AI | Expected routing |
|----|-------|-------------|------------------|
| 1 | IT / VPN–password | dept **IT**, high confidence | `pending_assignment` → IT |
| 2 | HR harassment | dept **HR**, `is_hr_sensitive` | **force** `pending_review` + highly confidential |
| 3 | Finance invoice / PO | dept **FIN** | `pending_assignment` → FIN |
| 4 | Fleet / pool car | dept **FLEET** | `pending_assignment` → FLEET |
| 5 | Legal NDA / compliance (+ injection text in security tests) | dept **LEGAL** | `pending_assignment` → LEGAL |
| 6 | Ambiguous “Need help” | null dept, low confidence | `pending_review` + `clarification_required` |

## How to run

```bash
cd backend
source .venv/bin/activate
export APP_ENV=test UPLOAD_DIR=/tmp/aibrm-test-uploads
pytest -q tests/test_scenarios.py tests/test_security.py tests/test_authz_gaps.py
```

## Manual UI smoke

1. Login `employee@aibrm.example.com` / `DemoPass123!`
2. Submit scenario 1 title → expect pending assignment (IT).
3. Submit scenario 6 → Review queue (admin/reviewer).
4. Submit scenario 2 → HR dashboard / review; notes hidden from employee.
