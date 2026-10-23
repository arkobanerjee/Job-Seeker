import tempfile
import unittest
from pathlib import Path
from pydantic import ValidationError
from job_seeker.settings import CompanyProfile,Companies
from job_seeker.registry import Registry

class QualificationTests(unittest.TestCase):
    def test_alias_migration_and_observed_official_ats_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry=Registry(Path(tmp)/'registry.sqlite3');url='https://jobs.lever.co/example/abc'
            registry.ingest('one',[{'company':'Example GmbH','url':url}],{})
            registry.configure_profiles([CompanyProfile(name='Example',aliases=['Example GmbH'],official_domains=['example.org'])])
            registry.ingest('two',[],{'https://example.org/careers':{'http_status':200,'text':'Jobs','links':['https://jobs.lever.co/example']}})
            company=registry.export()['companies'][0]
            self.assertEqual(len(registry.export()['companies']),1);self.assertEqual(company['name'],'Example')
            self.assertEqual(company['source_evidence'][0]['status'],'linked_from_official_domain')
    def test_similar_hostname_and_other_tenant_do_not_qualify(self):
        from job_seeker.qualification import qualify
        profile={'official_domains':['example.org']}
        self.assertEqual(qualify('https://example.org.evil.com/job',profile,[])['status'],'unverified')
        self.assertEqual(qualify('https://jobs.lever.co/other/abc',profile,[('https://example.org/careers','https://jobs.lever.co/example')])['status'],'unverified')
    def test_shared_ats_domains_and_ambiguous_aliases_rejected(self):
        with self.assertRaises(ValidationError):CompanyProfile(name='Example',official_domains=['jobs.lever.co'])
        with self.assertRaises(ValidationError):Companies(profiles=[CompanyProfile(name='One',aliases=['Same']),CompanyProfile(name='Two',aliases=['Same'])])
