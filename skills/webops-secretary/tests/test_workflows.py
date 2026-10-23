"""Reproducible workflow tests: standard library only, no browser or network."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "scripts"))

from simulated_browser import (  # noqa: E402
    AmbiguousSubmission, SimulatedBrowser, SimulatedSite, StaleObservation,
    TransientNavigationError, UnresolvedOperation, WorkflowError,
)


class BrowserWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.browser = SimulatedBrowser()

    def prepare_form(self, browser=None, label="Fictional equipment batch"):
        browser = browser if browser is not None else self.browser
        browser.navigate_with_recovery(browser.FORM)
        browser.fill(browser.site.label_field, label, browser.inspect())
        browser.fill("Category", "Inventory", browser.inspect())
        return browser

    def test_navigation_requires_current_observation(self):
        with self.assertRaises(StaleObservation):
            self.browser.navigate(self.browser.FORM, None)
        observed = self.browser.inspect()
        result = self.browser.navigate(self.browser.FORM, observed)
        self.assertEqual(result.path, self.browser.FORM)
        with self.assertRaises(StaleObservation):
            self.browser.fill("Label", "Fictional label", observed)

    def test_observations_cannot_cross_browser_instances(self):
        other = SimulatedBrowser()
        with self.assertRaises(StaleObservation):
            self.browser.navigate(self.browser.FORM, other.inspect())

    def test_form_fill_submit_and_verify(self):
        self.prepare_form()
        receipt = self.browser.submit("operation-000001", self.browser.inspect())
        self.assertEqual(receipt.label, "Fictional equipment batch")
        self.assertEqual(receipt.category, "Inventory")
        self.assertEqual(
            self.browser.lookup_submission("operation-000001", self.browser.inspect()), receipt
        )
        self.assertEqual(len(self.browser.site.records), 1)

    def test_form_validation_prevents_partial_commit(self):
        self.browser.navigate_with_recovery(self.browser.FORM)
        with self.assertRaises(ValueError):
            self.browser.submit("operation-000001", self.browser.inspect())
        self.browser.fill("Label", "Fictional label", self.browser.inspect())
        self.browser.fill("Category", "Unobserved category", self.browser.inspect())
        with self.assertRaises(ValueError):
            self.browser.submit("operation-000001", self.browser.inspect())
        self.assertEqual(self.browser.site.records, {})
        self.assertEqual(self.browser.site.submission_attempts, 0)

    def test_small_explicit_upload_and_receipt(self):
        self.prepare_form()
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fictional-inventory.csv"
            fixture.write_text("item,quantity\nDEMO-001,3\n", encoding="utf-8")
            upload = self.browser.upload(fixture, self.browser.inspect())
        receipt = self.browser.submit("operation-upload1", self.browser.inspect())
        self.assertEqual(receipt.attachment, upload)
        self.assertEqual(upload.name, "fictional-inventory.csv")
        self.assertEqual(len(upload.sha256), 64)
        self.assertNotIn(directory, repr(receipt))

    def test_upload_rejects_wrong_type_empty_binary_and_oversize(self):
        self.prepare_form()
        with tempfile.TemporaryDirectory() as directory:
            fixtures = {
                "fixture.exe": b"fictional executable",
                "empty.txt": b"",
                "binary.txt": b"demo\x00binary",
                "bad-utf8.txt": b"\xff\xfe",
                "oversize.csv": b"x" * (self.browser.MAX_UPLOAD_BYTES + 1),
            }
            for name, content in fixtures.items():
                with self.subTest(name=name):
                    fixture = Path(directory) / name
                    fixture.write_bytes(content)
                    with self.assertRaises(ValueError):
                        self.browser.upload(fixture, self.browser.inspect())
                    self.assertIsNone(self.browser.attachment)

    def test_transient_navigation_recovers(self):
        self.browser.navigation_failures = 2
        observed = self.browser.navigate_with_recovery(self.browser.FORM, max_attempts=3)
        self.assertEqual(observed.path, self.browser.FORM)
        self.assertEqual(self.browser.navigation_failures, 0)

    def test_navigation_recovery_is_bounded(self):
        self.browser.navigation_failures = 5
        with self.assertRaises(TransientNavigationError):
            self.browser.navigate_with_recovery(self.browser.FORM, max_attempts=2)
        self.assertEqual(self.browser.navigation_failures, 3)
        with self.assertRaises(ValueError):
            self.browser.navigate_with_recovery(self.browser.FORM, max_attempts=100)

    def test_interface_change_requires_new_inspection_and_mapping(self):
        self.browser.navigate_with_recovery(self.browser.FORM)
        old = self.browser.inspect()
        self.browser.site.change_interface()
        with self.assertRaises(StaleObservation):
            self.browser.fill("Label", "Fictional label", old)
        current = self.browser.inspect()
        self.assertIn("Display label", current.field_labels)
        self.assertEqual(current.interface_revision, 2)
        with self.assertRaises(WorkflowError):
            self.browser.fill("Label", "Fictional label", current)
        self.browser.fill("Display label", "Fictional label", self.browser.inspect())

    def test_timeout_requires_reconciliation_without_second_submit(self):
        self.prepare_form()
        self.browser.timeout_after_commit = True
        with self.assertRaises(AmbiguousSubmission):
            self.browser.submit("operation-timeout1", self.browser.inspect())
        with self.assertRaises(UnresolvedOperation):
            self.browser.submit("operation-timeout1", self.browser.inspect())
        receipt = self.browser.lookup_submission("operation-timeout1", self.browser.inspect())
        self.assertIsNotNone(receipt)
        self.assertEqual(self.browser.site.submission_attempts, 1)
        self.assertEqual(len(self.browser.site.records), 1)

    def test_verified_duplicate_identifier_does_not_create_another_record(self):
        self.prepare_form()
        receipt = self.browser.submit("operation-dedup01", self.browser.inspect())
        self.prepare_form()
        repeated = self.browser.submit("operation-dedup01", self.browser.inspect())
        self.assertEqual(receipt, repeated)
        self.assertEqual(len(self.browser.site.records), 1)

    def test_duplicate_identifier_with_changed_inputs_fails(self):
        self.prepare_form()
        self.browser.submit("operation-conflict1", self.browser.inspect())
        self.prepare_form(label="Different fictional batch")
        with self.assertRaises(WorkflowError):
            self.browser.submit("operation-conflict1", self.browser.inspect())
        self.assertEqual(len(self.browser.site.records), 1)

    def test_authentication_and_permissions_are_not_bypassed(self):
        for options in ({"authenticated": False}, {"authorized": False}):
            with self.subTest(options=options):
                browser = SimulatedBrowser(**options)
                with self.assertRaises(PermissionError):
                    browser.navigate_with_recovery(browser.FORM)

    def test_arbitrary_and_external_routes_are_rejected(self):
        with self.assertRaises(ValueError):
            self.browser.navigate("https://example.invalid/", self.browser.inspect())

    def test_resume_on_new_browser_verifies_server_state_first(self):
        self.prepare_form()
        self.browser.timeout_after_commit = True
        with self.assertRaises(AmbiguousSubmission):
            self.browser.submit("operation-resume01", self.browser.inspect())
        resumed = SimulatedBrowser(site=self.browser.site)
        receipt = resumed.lookup_submission("operation-resume01", resumed.inspect())
        self.assertIsNotNone(receipt)
        self.assertEqual(resumed.site.submission_attempts, 1)


class PersistentWorkflowTests(unittest.TestCase):
    """Journal real simulator results; recover before deciding to submit again."""

    ORIGIN = "https://portal.example.test"
    SCOPE = "fictional-inventory"

    def setUp(self):
        from memory import Store

        self.Store = Store
        self.directory = tempfile.TemporaryDirectory(prefix="webops-private-")
        self.addCleanup(self.directory.cleanup)
        self.private_root = Path(self.directory.name) / "memory"

    def store(self):
        return self.Store(root=self.private_root, public_roots=(ROOT,))

    def filled_browser(self, site=None):
        browser = SimulatedBrowser(site=site)
        browser.navigate_with_recovery(browser.FORM)
        browser.fill(browser.site.label_field, "Fictional sample batch", browser.inspect())
        browser.fill("Category", "Inventory", browser.inspect())
        return browser

    def test_verified_receipt_survives_store_restart(self):
        browser = self.filled_browser()
        with self.store() as memory:
            task = memory.create_task(self.SCOPE, self.ORIGIN, "Register a fictional inventory sample")
            memory.plan(task, "create-sample-001", "Submit the fictional sample form")
            memory.start(task, "create-sample-001")
            receipt = browser.submit("create-sample-001", browser.inspect())
            verified = browser.lookup_submission(receipt.operation_id, browser.inspect())
            self.assertEqual(verified, receipt)
            memory.resolve(task, "create-sample-001", "verified", f"Verified fictional receipt {receipt.record_id}")
            memory.checkpoint(task, "complete", "Verified one fictional sample record")
        with self.store() as memory:
            state = memory.resume(task)
            self.assertEqual(len(state["completed"]), 1)
            self.assertEqual(state["uncertain"], [])
            self.assertEqual(state["pending"], [])
            with self.assertRaises(ValueError):
                memory.start(task, "create-sample-001")
        self.assertEqual(browser.site.submission_attempts, 1)

    def test_interruption_after_submit_reconciles_before_retry(self):
        browser = self.filled_browser()
        browser.timeout_after_commit = True
        with self.store() as memory:
            task = memory.create_task(self.SCOPE, self.ORIGIN, "Register a fictional sample once")
            memory.plan(task, "resume-sample-001", "Submit the fictional sample form once")
            memory.start(task, "resume-sample-001")
            with self.assertRaises(AmbiguousSubmission):
                browser.submit("resume-sample-001", browser.inspect())
            # Simulate process interruption before recording any response.
        resumed_browser = SimulatedBrowser(site=browser.site)
        with self.store() as memory:
            state = memory.resume(task)
            self.assertEqual(len(state["uncertain"]), 1)
            self.assertEqual(state["completed"], [])
            with self.assertRaises(ValueError):
                memory.start(task, "resume-sample-001")
            receipt = resumed_browser.lookup_submission("resume-sample-001", resumed_browser.inspect())
            self.assertIsNotNone(receipt)
            memory.resolve(task, "resume-sample-001", "verified", f"Reconciled fictional receipt {receipt.record_id}")
            self.assertEqual(len(memory.resume(task)["completed"]), 1)
            self.assertEqual(memory.resume(task)["uncertain"], [])
        self.assertEqual(browser.site.submission_attempts, 1)
        self.assertEqual(len(browser.site.records), 1)

    def test_unknown_response_is_persisted_until_verification(self):
        browser = self.filled_browser()
        browser.timeout_after_commit = True
        with self.store() as memory:
            task = memory.create_task(self.SCOPE, self.ORIGIN, "Reconcile a fictional response timeout")
            memory.plan(task, "unknown-sample-01", "Submit and verify the fictional form")
            memory.start(task, "unknown-sample-01")
            with self.assertRaises(AmbiguousSubmission):
                browser.submit("unknown-sample-01", browser.inspect())
            memory.resolve(task, "unknown-sample-01", "unknown", "Response timed out; authoritative verification is pending")
        with self.store() as memory:
            self.assertEqual(len(memory.resume(task)["uncertain"]), 1)
            receipt = browser.lookup_submission("unknown-sample-01", browser.inspect())
            self.assertIsNotNone(receipt)
            memory.resolve(task, "unknown-sample-01", "verified", f"Verified fictional receipt {receipt.record_id}")
            self.assertEqual(len(memory.resume(task)["completed"]), 1)
        self.assertEqual(browser.site.submission_attempts, 1)

    def test_playbook_is_recalled_and_invalidated_after_interface_change(self):
        browser = self.filled_browser()
        receipt = browser.submit("learn-sample-001", browser.inspect())
        self.assertIsNotNone(browser.lookup_submission(receipt.operation_id, browser.inspect()))
        with self.store() as memory:
            memory.save_playbook(
                self.SCOPE, self.ORIGIN, "inventory-form",
                "Inspect the current form. Fill Label and Category. Verify the resulting record.",
                interface_version="1", confidence="medium", validated=True,
                evidence=f"Verified fictional receipt {receipt.record_id}",
            )
        browser.site.change_interface()
        with self.store() as memory:
            recalled = memory.recall(self.SCOPE, self.ORIGIN)
            self.assertEqual(len(recalled), 1)
            self.assertEqual(memory.recall("unrelated-scope", self.ORIGIN), [])
            self.assertEqual(memory.recall(self.SCOPE, "https://other.example.test"), [])
            memory.invalidate_playbook(
                self.SCOPE, self.ORIGIN, "inventory-form",
                "Interface revision changed from 1 to 2; inspect Display label before reuse",
            )
            # Invalidation removes it from normal recall or explicitly marks it stale.
            after = memory.recall(self.SCOPE, self.ORIGIN)
            self.assertTrue(not after or after != recalled)


if __name__ == "__main__":
    unittest.main()
