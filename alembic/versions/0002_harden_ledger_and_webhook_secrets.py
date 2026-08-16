"""harden ledger and webhook secrets

Revision ID: 0002_harden_ledger_webhooks
Revises: 0001_initial_schema
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_harden_ledger_webhooks"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "journals",
        sa.Column("status", sa.String(16), nullable=False, server_default="POSTED"),
    )
    op.add_column("journals", sa.Column("posted_at", sa.DateTime(timezone=True)))
    op.execute("update journals set posted_at = coalesce(posted_at, created_at)")
    op.create_check_constraint("ck_journal_status", "journals", "status in ('DRAFT', 'POSTED')")

    op.create_table(
        "webhook_secrets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "endpoint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("endpoint_id", "version", name="uq_webhook_secret_endpoint_version"),
    )
    op.create_index("ix_webhook_secrets_endpoint_id", "webhook_secrets", ["endpoint_id"])
    op.create_index(
        "uq_webhook_secret_active_endpoint",
        "webhook_secrets",
        ["endpoint_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )

    op.execute(
        """
        create or replace function enforce_posted_journal_balances()
        returns trigger
        language plpgsql
        as $$
        declare
          debit_total bigint;
          credit_total bigint;
          bad_currency_count integer;
        begin
          if new.status <> 'POSTED' then
            return new;
          end if;

          select
            coalesce(sum(amount_minor) filter (where direction = 'DEBIT'), 0),
            coalesce(sum(amount_minor) filter (where direction = 'CREDIT'), 0),
            count(*) filter (where currency <> new.currency)
          into debit_total, credit_total, bad_currency_count
          from journal_entries
          where journal_id = new.id;

          if debit_total = 0 and credit_total = 0 then
            raise exception 'posted journal % must have entries', new.id;
          end if;
          if debit_total <> credit_total then
            raise exception 'posted journal % is unbalanced: debit %, credit %',
              new.id, debit_total, credit_total;
          end if;
          if bad_currency_count > 0 then
            raise exception 'posted journal % has entries with mismatched currency', new.id;
          end if;

          return new;
        end;
        $$;
        """
    )
    op.execute(
        """
        create constraint trigger trg_posted_journal_balances
        after insert or update of status on journals
        deferrable initially deferred
        for each row
        execute function enforce_posted_journal_balances();
        """
    )
    op.execute(
        """
        create or replace function prevent_posted_journal_mutation()
        returns trigger
        language plpgsql
        as $$
        declare
          journal_status text;
        begin
          if tg_table_name = 'journals' then
            if tg_op = 'DELETE' and old.status = 'POSTED' then
              raise exception 'posted journals are immutable';
            end if;
            if tg_op = 'UPDATE' and old.status = 'POSTED'
              and (new.reference_type <> old.reference_type
                or new.reference_id <> old.reference_id
                or new.currency <> old.currency
                or new.status <> old.status
                or new.posted_at is distinct from old.posted_at) then
              raise exception 'posted journals are immutable';
            end if;
            return new;
          end if;

          if tg_op = 'DELETE' then
            select status into journal_status from journals where id = old.journal_id;
          else
            select status into journal_status from journals where id = new.journal_id;
          end if;

          if journal_status = 'POSTED' then
            raise exception 'posted journal entries are immutable';
          end if;
          if tg_op = 'DELETE' then
            return old;
          end if;
          return new;
        end;
        $$;
        """
    )
    op.execute(
        """
        create trigger trg_posted_journal_no_update_delete
        before update or delete on journals
        for each row
        execute function prevent_posted_journal_mutation();
        """
    )
    op.execute(
        """
        create trigger trg_posted_entry_no_insert_update_delete
        before insert or update or delete on journal_entries
        for each row
        execute function prevent_posted_journal_mutation();
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_posted_entry_no_insert_update_delete on journal_entries")
    op.execute("drop trigger if exists trg_posted_journal_no_update_delete on journals")
    op.execute("drop trigger if exists trg_posted_journal_balances on journals")
    op.execute("drop function if exists prevent_posted_journal_mutation()")
    op.execute("drop function if exists enforce_posted_journal_balances()")
    op.drop_index("uq_webhook_secret_active_endpoint", table_name="webhook_secrets")
    op.drop_index("ix_webhook_secrets_endpoint_id", table_name="webhook_secrets")
    op.drop_table("webhook_secrets")
    op.drop_constraint("ck_journal_status", "journals", type_="check")
    op.drop_column("journals", "posted_at")
    op.drop_column("journals", "status")
