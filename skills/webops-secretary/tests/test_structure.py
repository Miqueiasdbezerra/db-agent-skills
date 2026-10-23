"""Validate the portable entrypoint and all packaged source files offline."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_skill import validate


class StructureTests(unittest.TestCase):
    def test_entrypoint_frontmatter(self):
        content = (ROOT/'SKILL.md').read_text(encoding='utf-8')
        front = re.match(r'\A---\n(.*?)\n---\n',content,re.S)
        self.assertIsNotNone(front)
        self.assertRegex(front[1],r'(?m)^name: webops-secretary$')
        self.assertRegex(front[1],r'(?m)^description: .{15,}$')
        self.assertRegex(front[1],r'(?m)^  version: [\"\u0027]?1\.0\.0[\"\u0027]?$')
        self.assertLess(len(content.splitlines()),250)
        self.assertNotRegex(content,r'\[TODO:|\[INSERT HERE\]')

    def test_exact_manifest_links_and_source_syntax(self):
        payload = validate(ROOT)
        manifest = json.loads(payload['package-manifest.json'])
        self.assertEqual(set(payload),set(manifest['files']))
        for name, data in payload.items():
            with self.subTest(file=name):
                text = data.decode('utf-8')
                self.assertTrue(text.strip())
                if name.endswith('.py'): ast.parse(text,filename=name)

    def test_cli_help_has_no_network_or_installation_requirement(self):
        for script in ('memory.py','package_skill.py'):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),'--help'],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('usage:',result.stdout)


if __name__ == '__main__':
    unittest.main()
