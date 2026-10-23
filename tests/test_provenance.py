import unittest
from job_seeker.provenance import discovery_trails

class ProvenanceTests(unittest.TestCase):
    def test_direct_and_indirect_paths_preserve_query_and_rank(self):
        blog="https://example.org/blog"; job="https://example.org/jobs/ai"
        cache={"RAG companies Germany":[{"url":blog}],"AI Engineer jobs":[{"url":job}]}
        records={blog:{"links":[job]},job:{"observed_at":"2026-10-23"}}
        paths=discovery_trails(job,cache,records,"run")
        self.assertEqual(paths[0]["path"],[blog,job])
        self.assertEqual(paths[1]["path"],[job])
        self.assertEqual(paths[0]["query"],"RAG companies Germany")
        self.assertEqual(paths[0]["observed_at"],"2026-10-23")

    def test_cycles_and_missing_origins_do_not_invent_paths(self):
        a="https://example.org/a"; b="https://example.org/b"
        self.assertEqual(discovery_trails(b,{"query":[{"url":a}]},{a:{"links":[a]}},"run"),[])

    def test_redirect_and_normalized_url(self):
        a="https://example.org/old"; b="https://example.org/new"
        paths=discovery_trails(b,{"query":[{"url":a}]},{a:{"redirect":b}},"run")
        self.assertEqual(paths[0]["path"],[a,b])
