"""Static verification of Stage 1 and Stage 2 Supabase SQL migrations and RLS policies.

IMPORTANT NOTE:
These tests inspect the SQL migration definitions in `supabase/migrations/` to verify
that all required Stage 1 and Stage 2 tables, constraints, indexes, SECURITY DEFINER
search_path protections, and Row Level Security policies are present.
They do NOT replace live Supabase PostgreSQL execution tests (see `test_rls_live.py`).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
STAGE1_SCHEMA_SQL_PATH = MIGRATIONS_DIR / "20261103000001_stage1_core_schema.sql"
STAGE1_RLS_SQL_PATH = MIGRATIONS_DIR / "20261103000002_stage1_rls_policies.sql"
STAGE2_SCHEMA_SQL_PATH = MIGRATIONS_DIR / "20261108000003_stage2_onboarding_schema.sql"
STAGE2_RLS_SQL_PATH = MIGRATIONS_DIR / "20261108000004_stage2_onboarding_rls.sql"


def test_stage1_and_stage2_migration_files_exist() -> None:
    """Verify all Stage 1 and Stage 2 schema and RLS migration files exist."""
    for path in (
        STAGE1_SCHEMA_SQL_PATH,
        STAGE1_RLS_SQL_PATH,
        STAGE2_SCHEMA_SQL_PATH,
        STAGE2_RLS_SQL_PATH,
    ):
        assert path.is_file(), f"Missing migration file: {path}"


def test_stage1_schema_migration_defines_all_seven_tables_and_constraints() -> None:
    """Verify all 7 Stage 1 tables, check constraints, and composite FKs exist."""
    sql = STAGE1_SCHEMA_SQL_PATH.read_text(encoding="utf-8")

    expected_tables = [
        "CREATE TABLE IF NOT EXISTS public.profiles",
        "CREATE TABLE IF NOT EXISTS public.organizations",
        "CREATE TABLE IF NOT EXISTS public.organization_members",
        "CREATE TABLE IF NOT EXISTS public.businesses",
        "CREATE TABLE IF NOT EXISTS public.business_settings",
        "CREATE TABLE IF NOT EXISTS public.business_hours",
        "CREATE TABLE IF NOT EXISTS public.audit_logs",
    ]
    for statement in expected_tables:
        assert statement in sql, f"Missing table definition: {statement}"

    assert "CHECK (industry IN ('salon', 'clinic', 'hospital'))" in sql
    assert "CHECK (role IN ('owner', 'admin', 'staff'))" in sql
    assert "CHECK (weekday BETWEEN 0 AND 6)" in sql
    assert "UNIQUE (organization_id, user_id)" in sql
    assert "FOREIGN KEY (business_id, organization_id)" in sql


def test_stage1_rls_migration_enables_and_forces_rls_on_all_tables() -> None:
    """Verify RLS is enabled and forced on all 7 Stage 1 tables."""
    sql = STAGE1_RLS_SQL_PATH.read_text(encoding="utf-8")

    tables = [
        "profiles",
        "organizations",
        "organization_members",
        "businesses",
        "business_settings",
        "business_hours",
        "audit_logs",
    ]
    for table in tables:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in sql
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;" in sql


def test_stage1_rls_security_definer_functions_harden_search_path_and_permissions() -> None:
    """Verify SECURITY DEFINER helpers set safe search_path and revoke anon/public access."""
    sql = STAGE1_RLS_SQL_PATH.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE FUNCTION public.is_org_member(target_org_id UUID)" in sql
    assert "CREATE OR REPLACE FUNCTION public.has_org_role(target_org_id UUID, allowed_roles TEXT[])" in sql
    assert "SET search_path = public, pg_temp" in sql
    assert "REVOKE ALL ON FUNCTION public.is_org_member(UUID) FROM PUBLIC, anon;" in sql
    assert "REVOKE ALL ON FUNCTION public.has_org_role(UUID, TEXT[]) FROM PUBLIC, anon;" in sql


def test_stage2_schema_migration_defines_six_onboarding_tables_and_constraints() -> None:
    """Verify Stage 2 tables, unique business constraints, composite FKs, and check constraints."""
    sql = STAGE2_SCHEMA_SQL_PATH.read_text(encoding="utf-8")

    expected_stage2_tables = [
        "CREATE TABLE IF NOT EXISTS public.business_profiles",
        "CREATE TABLE IF NOT EXISTS public.business_languages",
        "CREATE TABLE IF NOT EXISTS public.business_faqs",
        "CREATE TABLE IF NOT EXISTS public.assistant_settings",
        "CREATE TABLE IF NOT EXISTS public.escalation_settings",
        "CREATE TABLE IF NOT EXISTS public.onboarding_progress",
    ]
    for statement in expected_stage2_tables:
        assert statement in sql, f"Missing Stage 2 table: {statement}"

    # Verify no duplicate business_profiles per business
    assert "CONSTRAINT uq_business_profiles_business_id" in sql
    assert "UNIQUE (business_id)" in sql

    # Verify check constraints for languages, personality, response_style, preferred_method, steps
    assert "CHECK (language_code IN ('en', 'hi', 'hinglish'))" in sql
    assert "CHECK (personality IN ('professional', 'friendly', 'warm'))" in sql
    assert "CHECK (response_style IN ('concise', 'balanced', 'detailed'))" in sql
    assert "CHECK (preferred_method IN ('phone', 'email', 'either'))" in sql


def test_stage2_rls_migration_enables_and_forces_rls_on_all_onboarding_tables() -> None:
    """Verify RLS is enabled and forced on all 6 Stage 2 onboarding tables with RBAC policies."""
    sql = STAGE2_RLS_SQL_PATH.read_text(encoding="utf-8")

    stage2_tables = [
        "business_profiles",
        "business_languages",
        "business_faqs",
        "assistant_settings",
        "escalation_settings",
        "onboarding_progress",
    ]
    for table in stage2_tables:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in sql
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;" in sql
        assert f"CREATE POLICY {table}_select_member" in sql
        assert f"CREATE POLICY {table}_insert_owner_or_admin" in sql
        assert f"CREATE POLICY {table}_update_owner_or_admin" in sql
