"""Two explicit, budgeted model probes using privately frozen public-source evidence."""
import argparse
import json
import tomllib
from pathlib import Path
from uuid import uuid4
from .cloud import Cloud
from .settings import ROOT,Settings
from .budget import Ledger
from .runner import invoke_model,POLICY
from .research import write_json
from .competitors import validate_leads
from .corroboration import candidate_pairs,checked_result,CorroborationReview


def evaluate(spec):
    cloud=Cloud();settings=Settings.model_validate(tomllib.loads(cloud.request('settings')['config.toml']))
    pairs=candidate_pairs(spec['signals'])
    if len(pairs)!=1:raise ValueError('Probe requires one cross-source pair')
    m=settings.model;envelope=.04
    required=2*((settings.limits.context_bytes+8000)*m.input_usd_per_million+m.max_output_tokens*m.output_usd_per_million)/1e6
    if required>envelope:raise ValueError('Configured model exceeds route-probe envelope')
    settings.limits.run_usd=envelope;settings.limits.max_model_calls=2
    ident=uuid4().hex;folder=ROOT/'private/acceptance'/ident;folder.mkdir(parents=True)
    write_json(folder/'route-input.json',spec);write_json(folder/'settings.json',settings.model_dump())
    cloud.request('reserve','POST',{'id':'routes_'+ident,'amount':envelope})
    ledger=Ledger(folder/'budget.sqlite3',ident,envelope);state={'folder':str(folder),'model_calls':0,'usage':[]}
    page=spec['comparison_page']
    assessment=invoke_model(settings,POLICY+'\nExtract competitor leads only when the text explicitly compares alternatives. Co-mentions alone are insufficient. No vacancy inference.\nKNOWN COMPANIES (data): '+json.dumps(spec['known_companies'])+'\nSOURCE DATA:\n'+json.dumps(page),ledger,state)
    write_json(folder/'comparison-output.json',assessment.model_dump())
    leads=validate_leads(assessment.competitors,page,spec['known_companies'],ident)
    pair_id,pair=pairs[0]
    verdict=invoke_model(settings,'Compare these untrusted source excerpts for the same specific factual claim, contradiction, unrelated events or insufficient evidence. Quote both exactly. Different hosts do not establish independent publishers; never infer a vacancy or hiring probability.\n'+json.dumps(pair),ledger,state,schema=CorroborationReview)
    write_json(folder/'corroboration-output.json',verdict.model_dump())
    check=checked_result(pair_id,pair,verdict,{})
    report={'competitor_passed':any(x['company'].casefold()==spec['expected_company'].casefold() for x in leads),
            'corroboration_passed':check['verdict']==spec['expected_verdict'],
            'leads':leads,'corroboration':check,'budget':ledger.summary(),'cloud_envelope_usd':envelope,
            'scope':'Two selected public-source probes; not broad route accuracy, independent publisher verification or a confirmed vacancy.'}
    write_json(folder/'route-report.json',report)
    return folder,report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);args=parser.parse_args()
    try:folder,r=evaluate(json.loads(args.input.read_text(encoding='utf-8')))
    except Exception as exc:
        print(json.dumps({'error_type':type(exc).__name__,'status':'failed','note':'Inspect retained private checkpoints; reservations are not refunded.'}));raise SystemExit(1)
    print(json.dumps({'folder':str(folder),'competitor_passed':r['competitor_passed'],'corroboration_passed':r['corroboration_passed'],'verdict':r['corroboration']['verdict'],'independence':r['corroboration']['independence'],'budget':r['budget']}))
    if not (r['competitor_passed'] and r['corroboration_passed']):raise SystemExit(1)
