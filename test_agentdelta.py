import json
import tempfile
import unittest
from pathlib import Path
from agentdelta import compare, load


def tool(actions=None, resources=None, approval='always'):
    return dict(name='research', actions=actions or ['read'], resources=resources or ['docs'], approval=approval)


class DeltaTests(unittest.TestCase):
    def test_unchanged(self):
        self.assertEqual(compare({'research': tool()}, {'research': tool()}), [])
    def test_escalation(self):
        f = compare({'research': tool()}, {'research': tool(['read','send'], ['*'], 'never')})
        self.assertEqual({x['rule'] for x in f}, {'ACTIONS_ADDED','RESOURCES_ADDED','APPROVAL_RELAXED','UNATTENDED_MUTATION'})
    def test_wildcard_already_present(self):
        self.assertEqual(compare({'research': tool(resources=['*'])}, {'research': tool(resources=['docs'])}), [])
    def test_restriction(self):
        self.assertEqual(compare({'research': tool(['read','write'], approval='never')}, {'research': tool()}), [])
    def test_removal(self):
        self.assertEqual(compare({'research': tool()}, {})[0]['rule'], 'TOOL_REMOVED')
    def test_new_tool(self):
        self.assertIn('TOOL_ADDED', {x['rule'] for x in compare({}, {'research':tool()})})
    def test_duplicate_names(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'; p.write_text(json.dumps({'tools':[tool(),tool()]}))
            with self.assertRaises(ValueError): load(p)
    def test_unknown_action(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'; p.write_text(json.dumps({'tools':[tool(['magic'])]}))
            with self.assertRaises(ValueError): load(p)
    def test_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'; p.write_text('{"tools":[]}')
            self.assertEqual(len(load(p)[1]),64)

if __name__ == '__main__': unittest.main()
