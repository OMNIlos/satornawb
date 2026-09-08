"""Pure assignment preconditions; this module performs no authorization or writes."""

from dataclasses import dataclass
from typing import Literal

from app.modules.orders import OrderContractValidationError


@dataclass(frozen=True, slots=True)
class AssignmentCommand:
    work_item_id: int
    expected_version: int
    idempotency_key: str
    catalog_sku_id: int
    reason: str

    def __post_init__(self):
        for value in (self.work_item_id, self.expected_version, self.catalog_sku_id):
            if type(value) is not int or value < 1:
                raise OrderContractValidationError(
                    "Positive command ID/version required"
                )
        for value in (self.idempotency_key, self.reason):
            if not isinstance(value, str) or not value or value != value.strip():
                raise OrderContractValidationError(
                    "Exact command key and reason required"
                )
            if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
                raise OrderContractValidationError(
                    "Assignment text is not PostgreSQL compatible"
                )


class OrderCommandConflict(OrderContractValidationError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_assignment_preconditions(
    command: AssignmentCommand,
    current_version: int,
    previous_command: AssignmentCommand | None = None,
) -> Literal["new", "replay"]:
    """Caller must authorize and read scoped idempotency/CAS state in one transaction."""
    if (
        not isinstance(command, AssignmentCommand)
        or type(current_version) is not int
        or current_version < 1
    ):
        raise OrderContractValidationError("Valid command and current version required")
    if previous_command is not None:
        if not isinstance(previous_command, AssignmentCommand):
            raise OrderContractValidationError("Stored command required")
        if (
            command.idempotency_key != previous_command.idempotency_key
            or command.work_item_id != previous_command.work_item_id
        ):
            raise OrderContractValidationError(
                "Stored command outside idempotency target scope"
            )
        if command == previous_command:
            return "replay"
        raise OrderCommandConflict("IDEMPOTENCY_CONFLICT")
    if command.expected_version != current_version:
        raise OrderCommandConflict("VERSION_CONFLICT")
    return "new"
