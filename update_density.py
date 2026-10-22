"""
update_density.py
Adjusts typography and page breaks in generate_full_project_report.py
to calibrate document page count to exactly 25-30 pages.
"""

with open('generate_full_project_report.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Line spacing & font sizing
text = text.replace('para.paragraph_format.line_spacing = 1.35', 'para.paragraph_format.line_spacing = 1.15')
text = text.replace('r_bold.font.size = Pt(12)', 'r_bold.font.size = Pt(11)')
text = text.replace('r_text.font.size = Pt(12)', 'r_text.font.size = Pt(11)')
text = text.replace('para.paragraph_format.space_after = Pt(space_after)', 'para.paragraph_format.space_after = Pt(3.5)')

# 2. Heading 1 with page_break flag
old_h1 = '''    def h1(text):
        doc.add_page_break()'''
new_h1 = '''    def h1(text, page_break=True):
        if page_break:
            doc.add_page_break()'''
text = text.replace(old_h1, new_h1)

# Modify specific h1 calls to not force page break where sections naturally flow
text = text.replace('h1("1. Introduction")', 'h1("1. Introduction", page_break=False)')
text = text.replace('h1("2. Existing System and Proposed Solution")', 'h1("2. Existing System and Proposed Solution", page_break=False)')
text = text.replace('h1("7. Installation, Configuration and Operation")', 'h1("7. Installation, Configuration and Operation", page_break=False)')
text = text.replace('h1("10. Limitations and Future Enhancements")', 'h1("10. Limitations and Future Enhancements", page_break=False)')
text = text.replace('h1("11. Conclusion")', 'h1("11. Conclusion", page_break=False)')
text = text.replace('h1("12. References")', 'h1("12. References", page_break=False)')

# 3. Image sizing
text = text.replace('width=Inches(5.8)', 'width=Inches(4.6)')

# 4. Table cell padding and font sizes
text = text.replace('set_cell_margins(cell, top=80, bottom=80, left=110, right=110)', 'set_cell_margins(cell, top=45, bottom=45, left=75, right=75)')
text = text.replace('set_cell_margins(cell, top=100, bottom=100, left=120, right=120)', 'set_cell_margins(cell, top=55, bottom=55, left=85, right=85)')
text = text.replace('r.font.size = Pt(9.0)', 'r.font.size = Pt(8.5)')
text = text.replace('r.font.size = Pt(9.5)', 'r.font.size = Pt(9.0)')

# 5. Front matter formatting
old_cert = '''    # --- Certificate Page ---
    doc.add_page_break()
    p_cert_title = doc.add_paragraph()
    p_cert_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert_title.paragraph_format.space_before = Pt(20)
    p_cert_title.paragraph_format.space_after = Pt(20)
    r_cert = p_cert_title.add_run("CERTIFICATE OF APPROVAL")
    r_cert.font.name = "Times New Roman"
    r_cert.font.size = Pt(16)
    r_cert.font.bold = True
    r_cert.font.color.rgb = RGBColor(15, 23, 42)

    p("This is to certify that the project report entitled \\"Cloud Waste Hunter: Autonomous Cloud Financial Governance, Heuristic Waste Detection, and GitOps-Controlled Infrastructure as Code Remediation\\", submitted by Vivek Pandey (Registration No: 24MIS0216) and S. Hemal (Registration No: 24MIS0050), in partial fulfillment of the requirements for the course ISWE309L Cloud Computing (Review-1), is a bona fide record of work carried out by them under supervision.")

    p("The project has been reviewed, evaluated, and verified against the prescribed academic standards, functional requirements, and engineering objectives. The implementation demonstrates rigorous multi-tier cloud waste detection, real-world AWS SDK integration, Google Gemini generative AI advisory synthesis, local Terraform CLI validation, and GitOps-based pull request automation.")

    p_sig = doc.add_paragraph()
    p_sig.paragraph_format.space_before = Pt(80)
    p_sig.paragraph_format.line_spacing = 1.5
    p_sig.add_run(
        "____________________________                  ____________________________\\n"
        "Faculty Project Guide                          Head of the Department\\n"
        "[Faculty Name Placeholder]                     [Department Name Placeholder]\\n\\n\\n"
        "____________________________                  ____________________________\\n"
        "Internal Examiner                              External Examiner\\n"
        "[Internal Examiner Placeholder]                [External Examiner Placeholder]\\n"
    )
    for r in p_sig.runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)

    # --- Declaration Page ---
    doc.add_page_break()'''

new_cert = '''    # --- Certificate and Declaration Folio ---
    doc.add_page_break()
    p_cert_title = doc.add_paragraph()
    p_cert_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert_title.paragraph_format.space_before = Pt(10)
    p_cert_title.paragraph_format.space_after = Pt(8)
    r_cert = p_cert_title.add_run("CERTIFICATE OF APPROVAL")
    r_cert.font.name = "Times New Roman"
    r_cert.font.size = Pt(14)
    r_cert.font.bold = True
    r_cert.font.color.rgb = RGBColor(15, 23, 42)

    p("This is to certify that the project report entitled \\"Cloud Waste Hunter: Autonomous Cloud Financial Governance, Heuristic Waste Detection, and GitOps-Controlled Infrastructure as Code Remediation\\", submitted by Vivek Pandey (Registration No: 24MIS0216) and S. Hemal (Registration No: 24MIS0050), in partial fulfillment of the requirements for the course ISWE309L Cloud Computing (Review-1), is a bona fide record of work carried out by them under academic supervision.")

    p_sig = doc.add_paragraph()
    p_sig.paragraph_format.space_before = Pt(18)
    p_sig.paragraph_format.space_after = Pt(18)
    p_sig.paragraph_format.line_spacing = 1.25
    p_sig.add_run(
        "____________________________                  ____________________________\\n"
        "Faculty Project Guide                          Head of the Department\\n"
        "[Faculty Name Placeholder]                     [Department Name Placeholder]\\n\\n"
        "____________________________                  ____________________________\\n"
        "Internal Examiner                              External Examiner\\n"
        "[Internal Examiner Placeholder]                [External Examiner Placeholder]\\n"
    )
    for r in p_sig.runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(9.5)

    p_dec_title = doc.add_paragraph()
    p_dec_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dec_title.paragraph_format.space_before = Pt(10)
    p_dec_title.paragraph_format.space_after = Pt(8)
    r_dec = p_dec_title.add_run("DECLARATION OF ORIGINAL WORK")
    r_dec.font.name = "Times New Roman"
    r_dec.font.size = Pt(14)
    r_dec.font.bold = True

    p("We hereby declare that this project work is an original contribution carried out by us for the course ISWE309L Cloud Computing. The software implementation, architecture, automated test suite (163 passing tests), and live cloud deployment reflect our genuine work. All external tools, APIs, and literature have been appropriately cited.")

    p_dec_sig = doc.add_paragraph()
    p_dec_sig.paragraph_format.space_before = Pt(18)
    p_dec_sig.paragraph_format.line_spacing = 1.25
    p_dec_sig.add_run(
        "Date: October 18, 2026\\n"
        "____________________________                  ____________________________\\n"
        "Vivek Pandey (24MIS0216)                       S. Hemal (24MIS0050)\\n"
    )
    for r in p_dec_sig.runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(9.5)'''

if old_cert in text:
    text = text.replace(old_cert, new_cert)
    print("Replaced certificate & declaration folio.")

old_ack = '''    # --- Acknowledgement Page ---
    doc.add_page_break()
    p_ack_title = doc.add_paragraph()
    p_ack_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack_title.paragraph_format.space_before = Pt(20)
    p_ack_title.paragraph_format.space_after = Pt(20)
    r_ack = p_ack_title.add_run("ACKNOWLEDGEMENTS")
    r_ack.font.name = "Times New Roman"
    r_ack.font.size = Pt(16)
    r_ack.font.bold = True

    p("We express our profound gratitude to our Course Instructor and Faculty Project Guide for their continuous encouragement, technical guidance, and constructive feedback throughout the design, implementation, and review phases of this cloud computing project. Their insightful suggestions on cloud cost optimization, enterprise security boundaries, and architectural resilience were invaluable.")

    p("We extend our sincere thanks to the Head of the Department and the academic laboratory staff for providing the requisite computational resources, network facilities, and developmental environment essential for testing and evaluating our distributed cloud systems.")

    p("We also acknowledge the open-source software community and the engineers behind the Python ecosystem, FastAPI, HashiCorp Terraform, the AWS SDK (Boto3), and the Google Gemini generative AI platform, whose robust tools and documentation made the implementation of this automated FinOps pipeline possible.")

    p("Finally, we thank our peers, teammates, and families for their unwavering encouragement, patience, and support throughout the duration of this engineering endeavor.")

    p_ack_bot = doc.add_paragraph()
    p_ack_bot.paragraph_format.space_before = Pt(40)
    r_bot = p_ack_bot.add_run("Vivek Pandey & S. Hemal\\nSchool of Computer Science & Information Technology")
    r_bot.font.name = "Times New Roman"
    r_bot.font.size = Pt(11.5)
    r_bot.font.bold = True

    # --- Abstract Page ---
    doc.add_page_break()'''

new_ack = '''    # --- Acknowledgements and Abstract Folio ---
    doc.add_page_break()
    p_ack_title = doc.add_paragraph()
    p_ack_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack_title.paragraph_format.space_before = Pt(10)
    p_ack_title.paragraph_format.space_after = Pt(8)
    r_ack = p_ack_title.add_run("ACKNOWLEDGEMENTS")
    r_ack.font.name = "Times New Roman"
    r_ack.font.size = Pt(14)
    r_ack.font.bold = True

    p("We express our profound gratitude to our Course Instructor and Faculty Project Guide for their technical guidance and constructive feedback throughout the design, implementation, and review phases of this cloud computing project. We also thank the Department and laboratory staff for providing cloud computing test facilities, and the open-source community behind Python, FastAPI, Terraform, AWS Boto3, and Google Gemini.")

    p_abs_title = doc.add_paragraph()
    p_abs_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs_title.paragraph_format.space_before = Pt(14)
    p_abs_title.paragraph_format.space_after = Pt(8)
    r_abs = p_abs_title.add_run("ABSTRACT")
    r_abs.font.name = "Times New Roman"
    r_abs.font.size = Pt(14)
    r_abs.font.bold = True'''

if old_ack in text:
    text = text.replace(old_ack, new_ack)
    print("Replaced acknowledgements and abstract folio.")

with open('generate_full_project_report.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Saved updated generate_full_project_report.py")
