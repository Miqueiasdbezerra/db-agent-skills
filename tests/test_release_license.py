"""Release gates protect the confirmed notice, terms and standalone distribution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('licensed_review', ROOT/'scripts/review_publication.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReleaseLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='webops-license-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'skills/webops-secretary').mkdir(parents=True)
        self.text = (ROOT/'LICENSE').read_text(encoding='utf-8')
        (self.root/'LICENSE').write_bytes(self.text.encode('utf-8'))
        (self.root/'skills/webops-secretary/LICENSE').write_bytes(self.text.encode('utf-8'))
        (self.root/'catalog.json').write_text(json.dumps({'license':{'effective_license':'MIT','copyright':review.COPYRIGHT,'normalized_sha256':review.LICENSE_SHA256}}),encoding='utf-8')

    def test_identical_approved_license_is_accepted(self):
        review.verify_licenses(self.root)
        # A platform checkout's line endings do not alter the actual terms.
        (self.root/'LICENSE').write_bytes(self.text.replace('\n','\r\n').encode('utf-8'))
        review.verify_licenses(self.root)

    def test_missing_or_inconsistent_standalone_license_is_rejected(self):
        path = self.root/'skills/webops-secretary/LICENSE'
        path.unlink()
        with self.assertRaises(FileNotFoundError): review.verify_licenses(self.root)
        path.write_text('MIT License\nIncomplete terms\n',encoding='utf-8')
        with self.assertRaises(ValueError): review.verify_licenses(self.root)

    def test_changed_owner_terms_or_metadata_are_rejected(self):
        for altered in (self.text.replace('Miqueias Durans Bezerra','Unconfirmed Fictional Owner'),self.text.replace('without warranty','with warranty')+'Changed terms\n'):
            with self.subTest(reason='altered-license'):
                for rel in ('LICENSE','skills/webops-secretary/LICENSE'):
                    (self.root/rel).write_bytes(altered.encode('utf-8'))
                with self.assertRaises(ValueError): review.verify_licenses(self.root)
        for rel in ('LICENSE','skills/webops-secretary/LICENSE'):
            (self.root/rel).write_bytes(self.text.encode('utf-8'))
        (self.root/'catalog.json').write_text('{"license":{"effective_license":"MIT","copyright":"Unconfirmed"}}',encoding='utf-8')
        with self.assertRaises(ValueError): review.verify_licenses(self.root)


if __name__ == '__main__':
    unittest.main()
