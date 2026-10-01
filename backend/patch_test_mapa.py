import re

with open('/media/akaun/Project_1/SEVALOR/backend/tests/test_phase2_torre_control_eval.py', 'r') as f:
    content = f.read()

# For the first part
content = re.sub(
    r"markers = map_res\.json\(\)\s*assert len\(markers\) >= 1\s*# Trobar el marcador de la nostra OT\s*ot_marker = next\(\(m for m in markers if m\[\"id\"\] == setup\[\"ot_id\"\]\), None\)",
    r"geojson = map_res.json()\n        assert geojson['type'] == 'FeatureCollection'\n        features = geojson['features']\n        assert len(features) >= 1\n        # Trobar el marcador de la nostra OT\n        ot_feature = next((f for f in features if f['properties']['id'] == setup['ot_id']), None)\n        ot_marker = ot_feature['properties'] if ot_feature else None\n        if ot_feature:\n            ot_marker['lat'] = ot_feature['geometry']['coordinates'][1]\n            ot_marker['lng'] = ot_feature['geometry']['coordinates'][0]",
    content
)

# For the second part
content = re.sub(
    r"assert map_b\.json\(\) == \[\]",
    r"assert map_b.json() == {'type': 'FeatureCollection', 'features': []}",
    content
)

with open('/media/akaun/Project_1/SEVALOR/backend/tests/test_phase2_torre_control_eval.py', 'w') as f:
    f.write(content)
