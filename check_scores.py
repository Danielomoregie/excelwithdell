import json

reg = json.load(open('src/models/model_registry.json'))
print('Run | Composite Score | Compared Against | Deployed')
for r in reg[-6:]:
    print(f"{r['run_number']:3d} | {r.get('composite_score', 'N/A'):15.6f} | {r.get('compared_against_score', 'N/A'):15.6f} | {r.get('deployed', False)}")
