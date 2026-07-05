import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

def get_card(pattern):
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else ''

metadata = get_card(r'<!-- METADATA & TREND STATUS -->.*?</div>\s+</div>\s+</div>')
calculator = get_card(r'<!-- 1-1-2-4 MARTIN CALCULATOR -->.*?</div>\s+</div>\s+</div>')
targets = get_card(r'<!-- TARGETS CARD -->.*?</div>\s+</div>\s+</div>')
settlement = get_card(r'<!-- SETTLEMENT CARD -->.*?</div>\s+</div>\s+</div>')
timeline = get_card(r'<!-- DAILY LOG TIMELINE CARD -->.*?</div>\s+</div>\s+</div>')

new_main = f'''<main class="dashboard-grid">
            
            <!-- LEFT PANEL: METADATA, TARGETS, TIMELINE -->
            <section class="panel-left">
                {metadata}

                {targets}

                {timeline}
            </section>

            <!-- RIGHT PANEL: CALCULATOR, SETTLEMENT -->
            <section class="panel-right">
                {calculator}

                {settlement}
            </section>
        </main>'''

new_content = re.sub(r'<main class="dashboard-grid">.*?</main>', new_main, content, flags=re.DOTALL)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('index.html rewritten')
