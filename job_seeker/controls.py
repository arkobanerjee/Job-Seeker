"""Cooperative boundaries: a tool already in flight is allowed to finish."""
class RunStopped(Exception):
    def __init__(self,action):self.action=action

def check_control(callback,run_id):
    action=callback(run_id) if callback else 'run'
    if action in ('pause','cancel'):raise RunStopped(action)
    if action!='run':raise ValueError('Invalid run control')
