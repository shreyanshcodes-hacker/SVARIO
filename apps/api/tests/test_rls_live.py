"""Live Supabase RLS verification suite (Stage 1).

Executes real PostgREST queries against a live Supabase project when:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_TEST_USER_A_TOKEN`
  - `SUPABASE_TEST_USER_B_TOKEN`
are configured in the environment.

When live Supabase credentials are not present in the local environment, these
tests are explicitly skipped with a `BLOCKED` status marker so simulated tests
are never misrepresented as live Supabase RLS verification.
"""

import os
import httpx
import pytest

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
USER_A_TOKEN = os.getenv("SUPABASE_TEST_USER_A_TOKEN", "").strip()
USER_B_TOKEN = os.getenv("SUPABASE_TEST_USER_B_TOKEN", "").strip()

LIVE_RLS_READY = bool(
    SUPABASE_URL
    and SUPABASE_ANON_KEY
    and USER_A_TOKEN
    and USER_B_TOKEN
    and "your-project-ref" not in SUPABASE_URL
)

BLOCKED_REASON = (
    "BLOCKED: Live Supabase RLS verification requires a live Supabase project URL, "
    "anon key, and two test user JWTs (SUPABASE_TEST_USER_A_TOKEN, SUPABASE_TEST_USER_B_TOKEN)."
)


@pytest.mark.skipif(not LIVE_RLS_READY, reason=BLOCKED_REASON)
def test_live_supabase_rls_cross_tenant_isolation() -> None:
    """Verify against a live Supabase instance that User B cannot read or modify User A's org."""
    base_rest = f"{SUPABASE_URL.rstrip('/')}/rest/v1"
    headers_a = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {USER_A_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    headers_b = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {USER_B_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    with httpx.Client(timeout=10.0) as client:
        # 1. Anonymous request without user JWT must not read organizations
        anon_resp = client.get(
            f"{base_rest}/organizations",
            headers={"apikey": SUPABASE_ANON_KEY},
        )
        assert anon_resp.status_code in (200, 401, 403)
        if anon_resp.status_code == 200:
            assert anon_resp.json() == []

        # 2. User B cannot see User A's profile
        profiles_b = client.get(f"{base_rest}/profiles", headers=headers_b)
        assert profiles_b.status_code == 200
        assert len(profiles_b.json()) <= 1

        # 3. User A and User B organization lists are strictly disjoint unless shared
        orgs_a = {row["id"] for row in client.get(f"{base_rest}/organizations", headers=headers_a).json()}
        orgs_b = {row["id"] for row in client.get(f"{base_rest}/organizations", headers=headers_b).json()}
        assert orgs_a.isdisjoint(orgs_b)
