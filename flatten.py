import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

def get_card(pattern):
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else ''

metadata = get_card(r'<div class="card metadata-card">.*?</div>\s+</div>\s+</div>')
calculator = get_card(r'<div class="card calculator-card">.*?</div>\s+</div>\s+</div>')
targets = get_card(r'<div class="card targets-card">.*?</div>\s+</div>\s+</div>')
settlement = get_card(r'<div class="card settlement-card">.*?</div>\s+</div>\s+</div>')
timeline = get_card(r'<div class="card timeline-card">.*?</div>\s+</div>\s+</div>')

new_main = f'''<main class="dashboard-grid">
            {metadata}
            {timeline}
            {targets}
            {settlement}
            {calculator}
        </main>'''

new_content = re.sub(r'<main class="dashboard-grid">.*?</main>', new_main, content, flags=re.DOTALL)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('index.html flattened')
