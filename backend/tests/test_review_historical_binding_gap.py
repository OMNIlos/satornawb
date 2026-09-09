"""Characterize an OPEN history-binding gap, not a safe-read acceptance test."""

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.integrations.publication_guard import (
    ExpectedAccountBinding,
    acquire_publication_guard,
)
from app.reviews.canonical_repository import ReviewFactsRepository, ReviewOwner
from tests import test_review_shadow_service as shadow

cluster = shadow.cluster
db = shadow.db
principal = shadow.principal
context = shadow.context


def test_completed_rebind_exposes_old_fact_under_new_live_read_guard(db, context):
    key = uuid4().hex
    ticket = shadow.start(db, context)
    shadow.api().publish_received_review_rows(
        db[1],
        ticket=ticket,
        rows=(shadow.row(key, "synthetic-old-cabinet-body"),),
        coverage=shadow.COVERAGE,
    )
    with db[0].begin() as connection:
        connection.execute(
            text(
                "UPDATE marketplace_accounts SET external_account_id='synthetic-new-cabinet' WHERE marketplace_account_id=91103"
            )
        )
        connection.execute(
            text(
                "UPDATE iam_memberships SET permissions='[\"reviews:read\"]' WHERE membership_id=:id"
            ),
            {"id": ticket.principal.membership_id},
        )
    with Session(db[1]) as session, session.begin():
        guard = acquire_publication_guard(
            session,
            principal=ticket.principal,
            required_permissions=frozenset({"reviews:read"}),
            accounts=(
                ExpectedAccountBinding(91103, "wb", "synthetic-new-cabinet", None),
            ),
            authorities=(),
        )
        guard.revalidate_before_write()
        repo = ReviewFactsRepository(
            session.connection(),
            ReviewOwner(91001, 91103, "wb", "synthetic-new-cabinet"),
            command_savepoints=False,
        )
        old = repo.get_fact(key)
    # This successful observation demonstrates the missing historical source binding.
    # A future safe reader must reject it; do not describe this PASS as isolation.
    assert old is not None
    assert old.text == "synthetic-old-cabinet-body"
