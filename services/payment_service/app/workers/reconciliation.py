import asyncio
import json
from pathlib import Path

from app.infra.database import SessionFactory
from app.infra.models import Journal, JournalEntry, Payment
from sqlalchemy import func, select


async def reconcile_once(output_dir: Path = Path("reconciliation-reports")) -> Path:
    output_dir.mkdir(exist_ok=True)
    findings: list[dict[str, object]] = []
    async with SessionFactory() as session:
        payments = await session.scalars(select(Payment))
        for payment in payments:
            captures = await session.scalar(
                select(func.coalesce(func.sum(JournalEntry.amount_minor), 0))
                .join(Journal, Journal.id == JournalEntry.journal_id)
                .where(
                    Journal.reference_type == "payment_capture",
                    Journal.reference_id == payment.id,
                    JournalEntry.direction == "CREDIT",
                )
            )
            if payment.status == "CAPTURED" and int(captures or 0) != payment.captured_amount_minor:
                findings.append(
                    {
                        "payment_id": str(payment.id),
                        "issue": "CAPTURED_PAYMENT_LEDGER_MISMATCH",
                        "payment_captured": payment.captured_amount_minor,
                        "ledger_captured": int(captures or 0),
                    }
                )
    path = output_dir / "latest.json"
    path.write_text(json.dumps({"findings": findings}, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(asyncio.run(reconcile_once()))
