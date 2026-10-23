"""Prepare private comparison inputs; never execute research or change production budgets."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    destination = ROOT / 'private/comparison'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('profile.md', 'resume.md'):
        shutil.copyfile(ROOT / 'private' / name, destination / name)
    shutil.copyfile(ROOT / 'prompts/master.md', destination / 'master.md')
    config = {
        'status': 'runner_available_live_execution_explicit',
        'total_budget_usd': 5.0,
        'budget_scope': 'all comparison configurations, repeats, searches, model calls and evaluators combined',
        'production_budget_access': False,
        'production_state_access': False,
        'notifications_enabled': False,
        'schedule_enabled': False,
        'model_provider': 'openai',
        'model': 'gpt-6-luna',
        'input_usd_per_million': 0.10,
        'output_usd_per_million': 0.50,
        'configurations': [
            {'id': 'A', 'research_workers': 1, 'coordination': 'sequential fixed subtasks'},
            {'id': 'B', 'research_workers': 2, 'coordination': 'parallel fixed subtasks'},
            {'id': 'C', 'research_workers': 2, 'coordination': 'shared coverage and bounded handoffs', 'enabled': False},
        ],
        'policy': 'Reserve worst-case cost before paid work; stop at cap; no automatic refunds or reset.',
    }
    (destination / 'experiment.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('Private comparison inputs prepared. No research executed.')

if __name__ == '__main__':
    main()
