import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

def get_card(pattern):
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else ''

metadata = get_card(r'<div class="card metadata-card">.*?</div>\s*</div>\s*</div>')
calculator = get_card(r'<div class="card calculator-card">.*?</div>\s*</div>\s*</div>')
targets = get_card(r'<div class="card targets-card">.*?</div>\s*</div>\s*</div>')
settlement = get_card(r'<div class="card settlement-card">.*?</div>\s*</div>\s*</div>')
timeline = get_card(r'<div class="card timeline-card">.*?</div>\s*</div>\s*</div>')

new_main = f'''<main class="dashboard-grid">
            
            <!-- LEFT PANEL: METADATA (종목분석), TIMELINE (메모기록) -->
            <section class="panel-left">
                {metadata}
                {timeline}
            </section>

            <!-- RIGHT PANEL: TARGETS (목표가/손절가), SETTLEMENT (매매결산), CALCULATOR (분할매수) -->
            <section class="panel-right">
                {targets}
                {settlement}
                {calculator}
            </section>

        </main>'''

new_content = re.sub(r'<main class="dashboard-grid">.*?</main>', new_main, content, flags=re.DOTALL)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('index.html restored to 2-column flexbox')
