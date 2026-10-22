"""
fine_tune_to_28.py
Brings the document to exactly 28-29 pages.
"""

with open('generate_full_project_report.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Line spacing & paragraph spacing
text = text.replace('para.paragraph_format.line_spacing = 1.12', 'para.paragraph_format.line_spacing = 1.08')
text = text.replace('para.paragraph_format.space_after = Pt(2.5)', 'para.paragraph_format.space_after = Pt(1.5)')

# 2. Image dimensions: width=Inches(3.8) for compact, elegant fit
text = text.replace('width=Inches(4.2)', 'width=Inches(3.8)')
text = text.replace('p_img.paragraph_format.space_before = Pt(8)', 'p_img.paragraph_format.space_before = Pt(4)')
text = text.replace('p_cap.paragraph_format.space_after = Pt(5)', 'p_cap.paragraph_format.space_after = Pt(3)')

# 3. Heading space
text = text.replace('para.paragraph_format.space_before = Pt(10)', 'para.paragraph_format.space_before = Pt(7)')
text = text.replace('para.paragraph_format.space_after = Pt(3)', 'para.paragraph_format.space_after = Pt(2)')

text = text.replace('para.paragraph_format.space_before = Pt(8)', 'para.paragraph_format.space_before = Pt(5)')
text = text.replace('para.paragraph_format.space_after = Pt(2)', 'para.paragraph_format.space_after = Pt(1)')

# 4. Table cell padding
text = text.replace('set_cell_margins(cell, top=45, bottom=45, left=75, right=75)', 'set_cell_margins(cell, top=35, bottom=35, left=65, right=65)')
text = text.replace('set_cell_margins(cell, top=55, bottom=55, left=85, right=85)', 'set_cell_margins(cell, top=45, bottom=45, left=75, right=75)')

with open('generate_full_project_report.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Applied fine-tuning for 28-29 pages.')
