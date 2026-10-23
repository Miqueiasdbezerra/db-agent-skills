"""Deterministic, offline browser model for WebOps Secretary examples and tests.

This module does not drive a browser, contact a website, or bypass authentication.
It models an authorized fictitious administrative form. Every action requires a
fresh inspection, and ambiguous submissions must be reconciled before retrying.
"""

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
from typing import Optional


class WorkflowError(RuntimeError):
    """An action cannot safely continue."""


class StaleObservation(WorkflowError):
    """The interface must be inspected again before acting."""


class TransientNavigationError(WorkflowError):
    """A simulated, recoverable navigation failure."""


class AmbiguousSubmission(WorkflowError):
    """The response was lost; success must be verified before another action."""


class UnresolvedOperation(WorkflowError):
    """A previous submission has an unknown outcome."""


@dataclass(frozen=True)
class Observation:
    """Visible interface data plus a token bound to this browser's current state."""

    path: str
    epoch: int
    interface_revision: int
    field_labels: tuple
    form_values: tuple
    visible_receipts: tuple
    token: object


@dataclass(frozen=True)
class UploadReceipt:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class SubmissionReceipt:
    record_id: str
    operation_id: str
    label: str
    category: str
    attachment: Optional[UploadReceipt]


class SimulatedSite:
    """Server state survives constructing another SimulatedBrowser instance."""

    def __init__(self):
        self.records = {}
        self.interface_revision = 1
        self.label_field = "Label"
        self.submission_attempts = 0

    def change_interface(self, label_field="Display label"):
        if not label_field.strip():
            raise ValueError("A visible field label is required")
        self.label_field = label_field
        self.interface_revision += 1


class SimulatedBrowser:
    """Small state machine with visible-state checks and bounded upload handling."""

    FORM = "/admin/records/new"
    LIST = "/admin/records"
    MAX_UPLOAD_BYTES = 64 * 1024
    ALLOWED_UPLOAD_SUFFIXES = frozenset({".txt", ".csv"})

    def __init__(self, site=None, *, authenticated=True, authorized=True):
        self.site = site if site is not None else SimulatedSite()
        self.authenticated = authenticated
        self.authorized = authorized
        self.path = self.LIST
        self.form = {"label": "", "category": ""}
        self.attachment = None
        self.navigation_failures = 0
        self.timeout_after_commit = False
        self.unresolved_operation = None
        self._epoch = 0
        self._token = object()
        self._latest = None

    def _check_access(self):
        if not self.authenticated:
            raise PermissionError("Sign-in is required; stop for the account owner")
        if not self.authorized:
            raise PermissionError("The account does not have permission")

    def _invalidate(self):
        self._epoch += 1
        self._latest = None

    def inspect(self):
        """Read only the simulated visible state; this does not act on the form."""
        self._check_access()
        labels = (self.site.label_field, "Category", "Attachment") if self.path == self.FORM else ()
        self._latest = Observation(
            self.path, self._epoch, self.site.interface_revision, labels,
            tuple(sorted(self.form.items())) if self.path == self.FORM else (),
            tuple(self.site.records.values()), self._token,
        )
        return self._latest

    def _require(self, observation):
        self._check_access()
        if (
            not isinstance(observation, Observation)
            or observation is not self._latest
            or observation.token is not self._token
            or observation.path != self.path
            or observation.epoch != self._epoch
            or observation.interface_revision != self.site.interface_revision
        ):
            raise StaleObservation("Inspect current state and remap visible controls")

    def navigate(self, path, observation):
        self._require(observation)
        if path not in (self.FORM, self.LIST):
            raise ValueError("Only the fictitious local admin routes are supported")
        self._invalidate()
        if self.navigation_failures:
            self.navigation_failures -= 1
            raise TransientNavigationError("Simulated temporary navigation failure")
        self.path = path
        return self.inspect()

    def navigate_with_recovery(self, path, *, max_attempts=3):
        """Retry only idempotent navigation, with a bounded number of attempts."""
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        for attempt in range(max_attempts):
            try:
                return self.navigate(path, self.inspect())
            except TransientNavigationError:
                if attempt == max_attempts - 1:
                    raise

    def fill(self, visible_label, value, observation):
        self._require(observation)
        if self.path != self.FORM:
            raise WorkflowError("Open the form before filling it")
        mapping = {self.site.label_field: "label", "Category": "category"}
        if visible_label not in mapping:
            raise WorkflowError("The observed field label no longer matches")
        if not isinstance(value, str):
            raise TypeError("Form values must be text")
        self.form[mapping[visible_label]] = value
        self._invalidate()

    def upload(self, file_path, observation):
        """Read a small, explicit fixture; no bytes or full local path are retained."""
        self._require(observation)
        if self.path != self.FORM:
            raise WorkflowError("Open the form before uploading")
        path = Path(file_path)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Upload must be a regular, explicitly supplied file")
        if path.suffix.lower() not in self.ALLOWED_UPLOAD_SUFFIXES:
            raise ValueError("Only .txt and .csv fixtures are supported")
        with path.open("rb") as stream:
            content = stream.read(self.MAX_UPLOAD_BYTES + 1)
        if not content or len(content) > self.MAX_UPLOAD_BYTES:
            raise ValueError("Upload fixture must contain 1 to 65536 bytes")
        if b"\x00" in content:
            raise ValueError("Upload fixture must be plain UTF-8 text")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Upload fixture must be plain UTF-8 text") from exc
        self.attachment = UploadReceipt(path.name, len(content), hashlib.sha256(content).hexdigest())
        self._invalidate()
        return self.attachment

    def submit(self, operation_id, observation):
        self._require(observation)
        if self.unresolved_operation:
            raise UnresolvedOperation("Verify the previous submission before continuing")
        if self.path != self.FORM:
            raise WorkflowError("Open the form before submitting")
        if not isinstance(operation_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", operation_id):
            raise ValueError("Use a stable, non-sensitive operation identifier")
        if not self.form["label"].strip() or len(self.form["label"]) > 100:
            raise ValueError("Label must contain 1 to 100 characters")
        if self.form["category"] not in ("Operations", "Inventory"):
            raise ValueError("Choose an observed, supported category")
        previous = self.site.records.get(operation_id)
        if previous and (
            previous.label != self.form["label"].strip()
            or previous.category != self.form["category"]
            or previous.attachment != self.attachment
        ):
            raise WorkflowError("The operation identifier already belongs to different inputs")
        self.site.submission_attempts += 1
        receipt = previous or SubmissionReceipt(
            f"demo-{len(self.site.records) + 1:04d}", operation_id,
            self.form["label"].strip(), self.form["category"], self.attachment,
        )
        self.site.records[operation_id] = receipt
        self._invalidate()
        if self.timeout_after_commit:
            self.timeout_after_commit = False
            self.unresolved_operation = operation_id
            raise AmbiguousSubmission("Simulated response timeout after the server committed")
        self.path = self.LIST
        return receipt

    def lookup_submission(self, operation_id, observation):
        """Reconcile against authoritative simulated records before retrying."""
        self._require(observation)
        receipt = self.site.records.get(operation_id)
        if receipt and self.unresolved_operation == operation_id:
            self.unresolved_operation = None
            self._invalidate()
        return receipt


def run_demo():
    browser = SimulatedBrowser()
    browser.navigate_with_recovery(browser.FORM)
    browser.fill("Label", "Fictional inventory sample", browser.inspect())
    browser.fill("Category", "Inventory", browser.inspect())
    receipt = browser.submit("demo-operation-0001", browser.inspect())
    assert browser.lookup_submission(receipt.operation_id, browser.inspect()) == receipt
    print(f"Verified fictional record: {receipt.record_id}; no network was used.")


if __name__ == "__main__":
    run_demo()
