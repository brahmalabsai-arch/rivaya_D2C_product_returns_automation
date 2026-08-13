import json
import os

with open('n8n/rivaya-returns-adjudication.json', 'r', encoding='utf-8') as f:
    adj = json.load(f)

with open('n8n/rivaya-returns-daily-digest.json', 'r', encoding='utf-8') as f:
    dig = json.load(f)

# Rename 'Config' to 'Digest Config' in digest nodes
for node in dig['nodes']:
    if node['name'] == 'Config':
        node['name'] = 'Digest Config'
    
    # Update jsCode in 'Get metrics' and 'Build digest' to refer to 'Digest Config'
    if 'jsCode' in node.get('parameters', {}):
        node['parameters']['jsCode'] = node['parameters']['jsCode'].replace("$('Config')", "$('Digest Config')")

    # Update url in 'Get metrics' to refer to 'Digest Config'
    if 'url' in node.get('parameters', {}):
        node['parameters']['url'] = node['parameters']['url'].replace("$('Config')", "$('Digest Config')")

# Rename in connections
new_dig_connections = {}
for src, targets in dig['connections'].items():
    new_src = 'Digest Config' if src == 'Config' else src
    new_targets = {}
    for conn_type, output_array in targets.items():
        new_output_array = []
        for links in output_array:
            new_links = []
            for link in links:
                new_link = dict(link)
                if new_link.get('node') == 'Config':
                    new_link['node'] = 'Digest Config'
                new_links.append(new_link)
            new_output_array.append(new_links)
        new_targets[conn_type] = new_output_array
    new_dig_connections[new_src] = new_targets

# Shift Y position of digest nodes so they don't overlap with adjudication nodes on canvas
for node in dig['nodes']:
    node['position'][1] += 1000

# Merge
combined = {
    'name': 'Rivaya Returns — Combined Workflow',
    'nodes': adj['nodes'] + dig['nodes'],
    'connections': {**adj['connections'], **new_dig_connections},
    'settings': adj['settings'],
    'meta': {'instanceId': 'rivaya-returns-combined-stage4'}
}

# Update adjudicatorUrl in both Config nodes to a placeholder for the user to fill in
for node in combined['nodes']:
    if node['name'] in ('Config', 'Digest Config'):
        for assignment in node['parameters'].get('assignments', {}).get('assignments', []):
            if assignment['name'] == 'adjudicatorUrl':
                assignment['value'] = 'https://YOUR_APP_NAME.onrender.com'

with open('n8n/rivaya-returns-combined.json', 'w', encoding='utf-8') as f:
    json.dump(combined, f, indent=2)

print('Combined workflow saved to n8n/rivaya-returns-combined.json')
