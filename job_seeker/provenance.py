"""Discovery evidence derived from saved observations, never model-generated."""
from .sources import normalized

def discovery_trails(url, cache, records, run_id):
    """Return bounded simple paths from search results to a recorded vacancy."""
    def norm(value):
        try: return normalized(value)
        except (ValueError, TypeError): return value
    target=norm(url); graph={}
    for key, record in records.items():
        parent=norm(key)
        children=list(record.get("links", []))
        final=record.get("final_url") or record.get("redirect")
        if final and norm(final)!=parent: children.append(final)
        graph[parent]=list(dict.fromkeys(norm(x) for x in children))
    trails=[]
    for query, results in cache.items():
        if not isinstance(results,list): continue
        for rank, result in enumerate(results,1):
            root=norm(result.get("url", "")); pending=[(root,[root])]
            while pending:
                current,path=pending.pop(0)
                if current==target:
                    trails.append({"run_id":run_id,"query":query,"result_rank":rank,
                        "search_title":result.get("title", ""),"path":path,
                        "observed_at":records.get(url,{}).get("observed_at"),
                        "basis":"saved_search_results_and_observed_links"})
                    break
                if len(path)>=8: continue
                for child in graph.get(current,[]):
                    if child not in path: pending.append((child,path+[child]))
                if len(pending)>500: pending=pending[:500]
            if len(trails)>=20: return trails
    return trails
