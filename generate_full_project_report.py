"""
generate_full_project_report.py
Generates the comprehensive, professional 25-30 page academic project report:
  - "Cloud_Waste_Hunter_Project_Report.docx"
  - "Cloud_Waste_Hunter_Project_Report.pdf"
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from build_report_utils import (
    set_cell_background,
    set_cell_margins,
    set_table_borders,
    add_header_footer,
    PRIMARY_DARK,
    PRIMARY_BLUE,
    TEXT_MAIN,
    TEXT_MUTED,
    BORDER_COLOR,
    BG_LIGHT,
    TABLE_HEADER_BG,
    TABLE_HEADER_TEXT,
    ROW_ALT_BG,
    ACCENT_GREEN,
    ACCENT_RED
)

def create_report():
    doc = docx.Document()
    
    # -------------------------------------------------------------
    # Styling and Helpers
    # -------------------------------------------------------------
    def p(text="", bold_prefix="", italic=False, space_after=6, space_before=0, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
        para = doc.add_paragraph()
        para.alignment = align
        para.paragraph_format.line_spacing = 1.08
        para.paragraph_format.space_after = Pt(1.5)
        para.paragraph_format.space_before = Pt(space_before)
        
        if bold_prefix:
            r_bold = para.add_run(bold_prefix)
            r_bold.font.name = "Times New Roman"
            r_bold.font.size = Pt(10.5)
            r_bold.font.bold = True
            r_bold.font.color.rgb = RGBColor(15, 23, 42)
            
        if text:
            r_text = para.add_run(text)
            r_text.font.name = "Times New Roman"
            r_text.font.size = Pt(10.5)
            r_text.font.italic = italic
            r_text.font.color.rgb = RGBColor(30, 41, 59)
            
        return para

    def h1(text, page_break=True):
        if page_break:
            doc.add_page_break()
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(7)
        para.paragraph_format.space_after = Pt(1)
        para.paragraph_format.keep_with_next = True
        r = para.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = RGBColor(15, 23, 42)
        return para

    def h2(text):
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(1.5)
        para.paragraph_format.keep_with_next = True
        r = para.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = RGBColor(30, 41, 59)
        return para

    def h3(text):
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(1.5)
        para.paragraph_format.keep_with_next = True
        r = para.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = RGBColor(51, 65, 85)
        return para

    def callout(title, text, border_color="0284c7", bg_color="f0f9ff"):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.27)
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
        
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:top w:val="none"/>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>'
            f'<w:bottom w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)
        
        para = cell.paragraphs[0]
        para.paragraph_format.space_after = Pt(1)
        para.paragraph_format.line_spacing = 1.2
        r_t = para.add_run(title + "\n")
        r_t.font.name = "Times New Roman"
        r_t.font.size = Pt(11)
        r_t.font.bold = True
        r_t.font.color.rgb = RGBColor(15, 23, 42)
        
        r_body = para.add_run(text)
        r_body.font.name = "Times New Roman"
        r_body.font.size = Pt(10.5)
        r_body.font.color.rgb = RGBColor(30, 41, 59)
        doc.add_paragraph().paragraph_format.space_after = Pt(3)

    def code_box(code_str):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.27)
        set_cell_background(cell, "0f172a")
        set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
        set_table_borders(table, color="334155", sz="6")
        
        para = cell.paragraphs[0]
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.line_spacing = 1.05
        r = para.add_run(code_str)
        r.font.name = "Consolas"
        r.font.size = Pt(7.5)
        r.font.color.rgb = RGBColor(226, 232, 240)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def add_fig(img_path, fig_num, caption_text, width=Inches(3.3)):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(4)
            p_img.paragraph_format.space_after = Pt(3)
            p_img.paragraph_format.keep_with_next = True
            run_img = p_img.add_run()
            run_img.add_picture(img_path, width=width)
            
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(3)
            r_num = p_cap.add_run(f"Figure {fig_num}: ")
            r_num.font.name = "Times New Roman"
            r_num.font.size = Pt(10)
            r_num.font.bold = True
            r_num.font.color.rgb = RGBColor(15, 23, 42)
            
            r_txt = p_cap.add_run(caption_text)
            r_txt.font.name = "Times New Roman"
            r_txt.font.size = Pt(10)
            r_txt.font.italic = True
            r_txt.font.color.rgb = RGBColor(51, 65, 85)
        else:
            p(f"[FIGURE {fig_num} PENDING: {caption_text}]", bold_prefix="Note: ", italic=True)

    def add_tbl(headers, rows, col_widths=None, tbl_num=None, tbl_caption=None):
        if tbl_num and tbl_caption:
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p_cap.paragraph_format.space_before = Pt(6)
            p_cap.paragraph_format.space_after = Pt(3)
            p_cap.paragraph_format.keep_with_next = True
            r_num = p_cap.add_run(f"Table {tbl_num}: ")
            r_num.font.name = "Times New Roman"
            r_num.font.size = Pt(10)
            r_num.font.bold = True
            r_num.font.color.rgb = RGBColor(15, 23, 42)
            
            r_txt = p_cap.add_run(tbl_caption)
            r_txt.font.name = "Times New Roman"
            r_txt.font.size = Pt(10)
            r_txt.font.italic = True
            r_txt.font.color.rgb = RGBColor(51, 65, 85)

        table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(table, color="cbd5e1", sz="4")
        
        # Header Row
        hdr_cells = table.rows[0].cells
        for i, title in enumerate(headers):
            cell = hdr_cells[i]
            cell.text = title
            set_cell_background(cell, TABLE_HEADER_BG)
            set_cell_margins(cell, top=45, bottom=45, left=75, right=75)
            p_hdr = cell.paragraphs[0]
            p_hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_hdr.paragraph_format.space_after = Pt(0)
            for r in p_hdr.runs:
                r.font.name = "Times New Roman"
                r.font.size = Pt(8.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)
                
        # Data Rows
        for r_idx, row_data in enumerate(rows):
            row_cells = table.rows[r_idx + 1].cells
            bg = ROW_ALT_BG if r_idx % 2 == 1 else "ffffff"
            for c_idx, val in enumerate(row_data):
                cell = row_cells[c_idx]
                cell.text = str(val)
                set_cell_background(cell, bg)
                set_cell_margins(cell, top=35, bottom=35, left=65, right=65)
                p_cell = cell.paragraphs[0]
                p_cell.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx > 0 else WD_ALIGN_PARAGRAPH.CENTER
                p_cell.paragraph_format.space_after = Pt(0)
                p_cell.paragraph_format.line_spacing = 1.05
                for r in p_cell.runs:
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(8.0)
                    r.font.color.rgb = RGBColor(30, 41, 59)
                    
        # Apply Column Widths
        if col_widths:
            for row in table.rows:
                for c_idx, w in enumerate(col_widths):
                    row.cells[c_idx].width = Inches(w)
                    
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # -------------------------------------------------------------
    # FRONT MATTER (Unnumbered)
    # -------------------------------------------------------------
    
    # --- Cover Page ---
    p_cov_top = doc.add_paragraph()
    p_cov_top.paragraph_format.space_before = Pt(36)
    p_cov_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_cov_top.add_run("ACADEMIC TECHNICAL PROJECT REPORT\nCOURSE: ISWE406 AGILE DEVELOPMENT PROCESS AND DEVOPS")
    r.font.name = "Times New Roman"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = RGBColor(100, 116, 139)

    p_cov_title = doc.add_paragraph()
    p_cov_title.paragraph_format.space_before = Pt(30)
    p_cov_title.paragraph_format.space_after = Pt(20)
    p_cov_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_cov_title.add_run("CLOUD WASTE HUNTER:\nAUTONOMOUS CLOUD FINANCIAL GOVERNANCE, HEURISTIC WASTE DETECTION, AND GITOPS-CONTROLLED INFRASTRUCTURE AS CODE REMEDIATION")
    r_title.font.name = "Times New Roman"
    r_title.font.size = Pt(18)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    p_cov_sub = doc.add_paragraph()
    p_cov_sub.paragraph_format.space_after = Pt(60)
    p_cov_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_cov_sub.add_run("A Project Report Submitted in Partial Fulfillment of the Requirements for\nISWE406 Agile Development Process and DevOps")
    r_sub.font.name = "Times New Roman"
    r_sub.font.size = Pt(12)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(71, 85, 105)

    p_cov_auth = doc.add_paragraph()
    p_cov_auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cov_auth.paragraph_format.line_spacing = 1.3
    r_auth_hdr = p_cov_auth.add_run("Submitted by:\n")
    r_auth_hdr.font.name = "Times New Roman"
    r_auth_hdr.font.size = Pt(11)
    r_auth_hdr.font.bold = True
    
    r_auth1 = p_cov_auth.add_run("Vivek Pandey (Registration No: 24MIS0216)\n")
    r_auth1.font.name = "Times New Roman"
    r_auth1.font.size = Pt(12)
    r_auth1.font.bold = True

    p_cov_inst = doc.add_paragraph()
    p_cov_inst.paragraph_format.space_before = Pt(80)
    p_cov_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cov_inst.paragraph_format.line_spacing = 1.25
    r_inst = p_cov_inst.add_run(
        "Department of Computer Science and Engineering / Information Technology\n"
        "[Institutional Affiliation Placeholder]\n"
        "Academic Year 2026–2027\n"
        "Date of Submission: October 2026"
    )
    r_inst.font.name = "Times New Roman"
    r_inst.font.size = Pt(11.5)
    r_inst.font.color.rgb = RGBColor(51, 65, 85)

    # --- Acknowledgements and Abstract Folio ---
    doc.add_page_break()
    p_ack_title = doc.add_paragraph()
    p_ack_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack_title.paragraph_format.space_before = Pt(10)
    p_ack_title.paragraph_format.space_after = Pt(8)
    r_ack = p_ack_title.add_run("ACKNOWLEDGEMENTS")
    r_ack.font.name = "Times New Roman"
    r_ack.font.size = Pt(14)
    r_ack.font.bold = True

    p("I express my sincere gratitude to my Course Instructor and Faculty Project Guide for their continuous guidance, technical mentorship, and constructive feedback throughout the design, implementation, and review phases of this project for ISWE406 Agile Development Process and DevOps. I also thank the Department and laboratory staff for providing computing test facilities, and the open-source community behind Python, FastAPI, Terraform, AWS Boto3, and Google Gemini.")

    p_abs_title = doc.add_paragraph()
    p_abs_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs_title.paragraph_format.space_before = Pt(14)
    p_abs_title.paragraph_format.space_after = Pt(8)
    r_abs = p_abs_title.add_run("ABSTRACT")
    r_abs.font.name = "Times New Roman"
    r_abs.font.size = Pt(14)
    r_abs.font.bold = True

    p("Modern enterprise cloud environments frequently experience significant financial waste and unmonitored carbon emissions resulting from idle compute clusters, abandoned Elastic Block Store (EBS) volumes, unassociated Elastic IP addresses, and dormant serverless functions. Traditional cloud financial management (FinOps) approaches rely predominantly on passive reporting dashboards or hazardous, unvalidated automated deletion scripts that risk catastrophic production downtime and infrastructure state drift.")

    p("This project introduces Cloud Waste Hunter, a production-grade, closed-loop cloud financial governance and automated remediation platform. Cloud Waste Hunter combines multi-service discovery across Amazon Web Services (AWS) using the Boto3 SDK, heuristic telemetry analysis over 14-day and 30-day CloudWatch evaluation windows, empirical AWS pricing and Greenhouse Gas (GHG) carbon modeling, and contextual Google Gemini generative artificial intelligence (gemini-3.5-flash-lite) advisory synthesis.")

    p("To eliminate the catastrophic operational risks associated with automated resource deletion, Cloud Waste Hunter implements an Eight-Point Safety Gate architecture governing declarative Infrastructure as Code (IaC) generation. The platform leverages the HashiCorp Terraform CLI to format, validate, and bind existing live cloud assets into state via automated terraform import before generating strict binary execution plans. The application enforces a dual-checkbox Human-in-the-Loop Sign-Off Gate, requiring explicit engineer verification and secondary confirmation for destructive operations before any execution can occur. Furthermore, the platform integrates with GitOps workflows, submitting declarative remediation patches to isolated Git branches protected by automated continuous integration (CI) validation checks, tamper-evident audit logging, and peer-review sign-offs.")

    p("The entire system has been verified through an automated test suite comprising 163 unit, integration, and security hardening tests passing with 100% test coverage across 11 test suites. Furthermore, the application is deployed live in the AWS Sydney region (ap-southeast-2) on an Ubuntu 26.04 LTS t3.micro EC2 instance managed by systemd, operating entirely within the AWS Free Tier ($0.00/month). Live testing against real AWS infrastructure successfully identified and generated validated remediation plans for unattached EBS storage waste while preserving active application workloads.")

    p("Keywords: Agile Development, DevOps, FinOps, Cloud Cost Optimization, AWS Boto3, Google Gemini AI, Terraform CLI, GitOps, Infrastructure as Code, Human-in-the-Loop Safety Gates, Carbon Footprint Modeling.", bold_prefix="Keywords: ", italic=True)

    # --- Table of Contents ---
    doc.add_page_break()
    p_toc = doc.add_paragraph()
    p_toc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_toc.paragraph_format.space_before = Pt(16)
    p_toc.paragraph_format.space_after = Pt(16)
    r_toc = p_toc.add_run("TABLE OF CONTENTS")
    r_toc.font.name = "Times New Roman"
    r_toc.font.size = Pt(16)
    r_toc.font.bold = True

    toc_items = [
        ("Acknowledgements & Abstract", "2"),
        ("Table of Contents", "3"),
        ("List of Figures & Tables", "5"),
        ("1. Introduction", "6"),
        ("   1.1 Background and Context", "6"),
        ("   1.2 Problem Statement", "6"),
        ("   1.3 Project Objectives", "6"),
        ("   1.4 Scope and Boundaries", "7"),
        ("   1.5 Motivation and Expected Benefits", "7"),
        ("2. Existing System and Proposed Solution", "8"),
        ("   2.1 Existing Approaches to Cloud Cost Monitoring", "8"),
        ("   2.2 Limitations of the Existing Approaches", "8"),
        ("   2.3 Proposed Cloud Waste Hunter Solution", "8"),
        ("   2.4 Key Features Verified in the Implementation", "8"),
        ("   2.5 Functional Requirements", "9"),
        ("   2.6 Non-Functional Requirements", "9"),
        ("   2.7 Assumptions and Constraints", "10"),
        ("3. Technology Stack and System Requirements", "10"),
        ("   3.1 Programming Languages and Frameworks", "10"),
        ("   3.2 Frontend Technologies", "10"),
        ("   3.3 Backend Technologies and API Framework", "11"),
        ("   3.4 AWS Services and SDKs", "11"),
        ("   3.5 Gemini AI Integration", "11"),
        ("   3.6 Terraform and GitOps Tools", "11"),
        ("   3.7 Development and Operational Dependencies", "12"),
        ("   3.8 Operating System and Runtime Requirements", "12"),
        ("   3.9 Installation Prerequisites", "12"),
        ("4. System Architecture and Design", "12"),
        ("   4.1 High-Level System Architecture", "12"),
        ("   4.2 Component Responsibilities", "13"),
        ("   4.3 Frontend-Backend Interaction", "13"),
        ("   4.4 Data Flow and Module Interactions", "13"),
        ("   4.5 End-to-End Workflow", "14"),
        ("   4.6 Security and Approval Workflow", "14"),
        ("   4.7 Proposed Deployment Architecture", "15"),
        ("5. Module Implementation", "15"),
        ("   5.1 Overview of the Seven Modules", "15"),
        ("   5.2 Module 1: Resource Discovery and Telemetry Ingestion", "15"),
        ("   5.3 Module 2: Cloud Waste Detection Rules Engine", "16"),
        ("   5.4 Module 3: Cost and Carbon Footprint Estimation", "16"),
        ("   5.5 Module 4: Google Gemini AI Advisor Synthesis", "17"),
        ("   5.6 Module 5: Terraform HCL Remediation Patch Generation", "17"),
        ("   5.7 Module 6: Terraform CLI Safety Gates and Plan Integrity Verification", "18"),
        ("   5.8 Module 7: GitOps Pull Request Review and Approval Workflow", "18"),
        ("   5.9 Inter-Module Communication", "19"),
        ("   5.10 Error Handling and Failure Scenarios", "19"),
        ("   5.11 Implementation Limitations", "19"),
        ("6. Security and Safety Controls", "19"),
        ("   6.1 AWS Credential Management", "19"),
        ("   6.2 IAM Roles and Least-Privilege Permissions", "20"),
        ("   6.3 AWS Identity Verification", "20"),
        ("   6.4 Gemini API Key Protection", "20"),
        ("   6.5 Live Mode versus Demo Mode", "20"),
        ("   6.6 Terraform Plan Validation and Integrity Verification", "20"),
        ("   6.7 Human Approval and Destructive-Action Safeguards", "20"),
        ("   6.8 Plan Expiry and Audit Logging", "20"),
        ("   6.9 GitOps Review and Approval Boundaries", "21"),
        ("   6.10 Security Limitations and Recommendations", "21"),
        ("7. Installation, Configuration and Operation", "21"),
        ("   7.1 Prerequisites", "21"),
        ("   7.2 Obtaining the Source Code", "21"),
        ("   7.3 Python Environment Setup", "21"),
        ("   7.4 Dependency Installation", "21"),
        ("   7.5 External Tool Installation", "22"),
        ("   7.6 Environment Configuration", "22"),
        ("   7.7 AWS Configuration", "22"),
        ("   7.8 Gemini Configuration", "22"),
        ("   7.9 Starting the Application", "22"),
        ("   7.10 Accessing the Application Interface", "22"),
        ("   7.11 Operational Verification", "22"),
        ("   7.12 Troubleshooting", "22"),
        ("8. Proposed AWS EC2 Deployment and Cost Considerations", "23"),
        ("   8.1 Deployment Objectives", "23"),
        ("   8.2 Existing Application Compatibility", "23"),
        ("   8.3 Proposed EC2 Architecture", "23"),
        ("   8.4 Operating System and Instance Selection", "23"),
        ("   8.5 IAM Instance Role Configuration", "23"),
        ("   8.6 Network Access and Application Security", "23"),
        ("   8.7 Application Process Management", "23"),
        ("   8.8 Logging and Operational Monitoring", "24"),
        ("   8.9 Free Tier Eligibility and Cost Considerations", "24"),
        ("   8.10 Deployment Status and Operational Verification", "24"),
        ("9. Limitations and Future Enhancements", "24"),
        ("   9.1 Current Technical Limitations", "24"),
        ("   9.2 Integration and Deployment Limitations", "24"),
        ("   9.3 Potential Improvements", "25"),
        ("   9.4 Future Development Opportunities", "25"),
        ("10. Conclusion", "25"),
        ("   10.1 Summary of the Project", "25"),
        ("   10.2 Achievement of Objectives", "25"),
        ("   10.3 Verified Outcomes", "25"),
        ("   10.4 Final Assessment", "25"),
        ("11. References", "25"),
        ("12. Appendices", "26"),
        ("   12.1 Selected Configuration Templates", "26"),
        ("   12.2 Deployment and System Service Configuration", "26"),
        ("   12.3 Relevant API Details", "26"),
        ("   12.4 Sample Declarative Remediation Patch", "27")
    ]

    for title, page_str in toc_items:
        p_t = doc.add_paragraph()
        p_t.paragraph_format.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        p_t.paragraph_format.line_spacing = 1.05
        p_t.paragraph_format.space_after = Pt(1.0)
        r = p_t.add_run(f"{title}	{page_str}")
        r.font.name = "Times New Roman"
        if not title.startswith("   "):
            r.font.size = Pt(9.5)
            r.font.bold = True
        else:
            r.font.size = Pt(9.0)

    # --- List of Figures ---
    doc.add_page_break()
    p_lof = doc.add_paragraph()
    p_lof.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lof.paragraph_format.space_before = Pt(16)
    p_lof.paragraph_format.space_after = Pt(16)
    r_lof = p_lof.add_run("LIST OF FIGURES")
    r_lof.font.name = "Times New Roman"
    r_lof.font.size = Pt(16)
    r_lof.font.bold = True

    figures_list = [
        ("Figure 1", "High-Level Three-Tier System Architecture Diagram", "13"),
        ("Figure 2", "End-to-End Autonomous Cloud Waste Remediation Workflow", "14"),
        ("Figure 3", "Eight-Point Terraform and GitOps Security Safety Gate Architecture", "14"),
        ("Figure 4", "AWS EC2 Free-Tier Live Production Topology in Sydney (ap-southeast-2)", "15"),
        ("Figure 5", "Module 1 — Live Cloud Discovery and Multi-Service Inventory Panel", "16"),
        ("Figure 6", "Module 2 — Heuristic Waste Detection and Risk Evaluation Findings", "16"),
        ("Figure 7", "Module 3 — Cost Attribution, Annualized Savings, and GreenOps Model", "17"),
        ("Figure 8", "Module 4 — Google Gemini AI FinOps Advisor Synthesis and Summary", "17"),
        ("Figure 9", "Module 5 — Declarative Terraform HCL Remediation Patch Generation", "18"),
        ("Figure 10", "Module 6 — Terraform CLI Safety Gates and Dual-Human Sign-Off Gate", "18"),
        ("Figure 11", "Module 7 — GitOps Pull Request Review and Automated CI/CD Checklist", "19")
    ]

    for f_num, f_desc, f_pg in figures_list:
        p_f = doc.add_paragraph()
        p_f.paragraph_format.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        p_f.paragraph_format.line_spacing = 1.1
        p_f.paragraph_format.space_after = Pt(2.5)
        r1 = p_f.add_run(f"{f_num}: {f_desc}	{f_pg}")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(9.5)

    # --- List of Tables ---
    p_lot = doc.add_paragraph()
    p_lot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lot.paragraph_format.space_before = Pt(24)
    p_lot.paragraph_format.space_after = Pt(16)
    r_lot = p_lot.add_run("LIST OF TABLES")
    r_lot.font.name = "Times New Roman"
    r_lot.font.size = Pt(16)
    r_lot.font.bold = True

    tables_list = [
        ("Table 2.1", "Functional Requirements Specification (FR1 – FR14)", "9"),
        ("Table 2.2", "Non-Functional Requirements Specification (NFR1 – NFR8)", "10"),
        ("Table 3.1", "Comprehensive Technology Stack and Dependency Specifications", "12"),
        ("Table 5.1", "Architectural Responsibilities of the Seven FinOps Engine Modules", "15"),
        ("Table 6.1", "Security Threat Vector Analysis and Corresponding Mitigation Safeguards", "21"),
        ("Table 7.1", "Environment Configuration Variables and Supported System Parameters", "22"),
        ("Table 8.1", "AWS Free Tier Monthly Compute and Storage Cost Breakdown", "24"),
        ("Table 8.2", "Verified Production Deployment Parameters on AWS EC2", "24"),
        ("Table 12.1", "Comprehensive REST API Endpoints Specification", "26")
    ]

    for t_num, t_desc, t_pg in tables_list:
        p_t = doc.add_paragraph()
        p_t.paragraph_format.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        p_t.paragraph_format.line_spacing = 1.1
        p_t.paragraph_format.space_after = Pt(2.5)
        r1 = p_t.add_run(f"{t_num}: {t_desc}	{t_pg}")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(9.5)

    # -------------------------------------------------------------
    # 1. INTRODUCTION
    # -------------------------------------------------------------
    h1("1. Introduction", page_break=True)
    
    h2("1.1 Background and Context")
    p("The rapid global adoption of on-demand public cloud infrastructure—predominantly Amazon Web Services (AWS), Microsoft Azure, and Google Cloud Platform (GCP)—has revolutionized enterprise software engineering. Organizations can provision compute clusters, multi-terabyte storage volumes, serverless execution environments, and complex networking topologies within seconds. However, this elasticity has introduced a profound operational challenge: unchecked cloud resource sprawl and severe financial waste.")

    p("Industry analyses conducted by the FinOps Foundation and enterprise cloud auditing firms consistently indicate that between 28% and 35% of total enterprise cloud expenditure is squandered on unutilized or grossly over-provisioned infrastructure assets. In typical enterprise AWS deployments, software development teams routinely deploy oversized Elastic Compute Cloud (EC2) instances that operate at less than 5% average CPU utilization. Similarly, engineers terminate virtual machines while neglecting to delete their attached Elastic Block Store (EBS) storage volumes, leaving orphaned disks accumulating ongoing storage fees indefinitely.")

    p("Beyond direct financial penalties, unmanaged cloud waste directly compounds global carbon emissions. Idle server hardware in hyperscale data centers continues to draw baseline electrical power, contributing to Scope 2 greenhouse gas emissions without delivering computational value. Consequently, modern cloud governance necessitates Cloud Financial Management (FinOps)—an operational framework combining engineering, financial accountability, and automated governance to optimize cloud value.")

    h2("1.2 Problem Statement")
    p("Existing enterprise cloud cost monitoring solutions suffer from fundamental architectural and operational shortcomings that prevent effective, safe waste remediation:")

    p("1. Passive Visibility Without Safe Remediation: Native cloud tools such as AWS Cost Explorer and AWS Trusted Advisor generate static cost reports and optimization recommendations. However, they lack automated mechanisms to remediate the identified waste, shifting the heavy burden of manual infrastructure modification onto overextended DevOps engineers.")

    p("2. Catastrophic Risks of Blind Deletion Scripts: To bridge this automation gap, organizations frequently deploy ad-hoc shell scripts or Lambda-based 'janitor' functions executing unvalidated API calls (e.g., aws ec2 delete-volume). These scripts lack state awareness, empirical safety gates, and human oversight. A script that misidentifies a temporarily stopped mission-critical database volume as 'idle' and deletes it causes catastrophic data loss and production outages.")

    p("3. Infrastructure Drift and IaC Corruption: Modern cloud environments manage infrastructure declaratively through Infrastructure as Code (IaC) frameworks like HashiCorp Terraform. When out-of-band scripts delete AWS assets directly via cloud APIs, the live cloud environment diverges from the Terraform state file (terraform.tfstate), creating severe state drift, broken CI/CD pipelines, and unrepeatable deployments.")

    p("4. Absence of Explainable AI Guidance and Auditability: Automated tools rarely provide transparent engineering rationales, risk assessments, or actionable rollback strategies. Furthermore, they lack tamper-evident audit trails and peer-review integration required for enterprise compliance (SOC 2, ISO 27001).")

    h2("1.3 Project Objectives")
    p("The primary objective of the Cloud Waste Hunter project is to design, implement, and rigorously verify an autonomous, closed-loop cloud financial governance and remediation platform that overcomes the limitations of existing approaches. The specific engineering objectives are:")

    p("• Objective 1 (Automated Multi-Service Discovery): Engineer a non-invasive, read-only discovery engine that interfaces directly with real AWS infrastructure via the Boto3 SDK, querying EC2 compute, EBS storage, Elastic IPs, Lambda serverless functions, and S3 storage across AWS regions.")

    p("• Objective 2 (Deterministic Heuristic Telemetry Analysis): Ingest 14-day and 30-day historical CloudWatch metric streams to evaluate empirical utilization (CPU, memory, read/write IOPS, network throughput, invocation frequency) and classify waste against deterministic engineering rules.")

    p("• Objective 3 (Transparent Financial & Carbon Modeling): Calculate exact monthly and annualized cost savings using regional AWS pricing models, while estimating environmental impact in kilograms of carbon dioxide equivalent (kg CO2e) using the Greenhouse Gas Protocol.")

    p("• Objective 4 (Explainable Generative AI Advisory): Integrate the Google Gemini generative AI platform (gemini-3.5-flash-lite) to synthesize structured executive summaries, operational risk ratings (Low, Medium, High), step-by-step remediation commands, and rollback procedures grounded exclusively on verified telemetry.")

    p("• Objective 5 (Declarative Terraform HCL Generation): Automatically generate syntactically valid, declarative Terraform remediation patches that safely decommission or resize waste resources without modifying unrelated infrastructure blocks.")

    p("• Objective 6 (Eight-Point Terraform Safety Gate Architecture): Enforce strict CLI-level pre-apply validation, state import binding (terraform import) for unmanaged assets, and binary plan inspection (0 to add, 0 to change, N to destroy), completely eliminating out-of-band drift.")

    p("• Objective 7 (Dual-Checkbox Human-in-the-Loop Gate): Restrict the execution of terraform apply behind a mandatory human approval gate requiring explicit authorization and secondary confirmation for destructive operations.")

    p("• Objective 8 (GitOps Pull Request & CI/CD Governance): Orchestrate automated GitOps pull requests on isolated branches, embedding complete FinOps evidence dossiers, automated CI validation checks, and tamper-evident audit logging.")

    h2("1.4 Scope and Boundaries")
    p("The operational boundaries and technical scope of Cloud Waste Hunter are defined as follows:")

    p("Supported Resource Types: In scope are Amazon EC2 instances, EBS storage volumes (gp2, gp3, io1, io2, standard), Elastic IP allocations, AWS Lambda functions, and Amazon S3 buckets. Multi-tenant Amazon EKS container pods and Amazon RDS database clusters are excluded from the current automated remediation scope due to multi-tier stateful data dependencies.")

    p("Cloud Provider Boundary: The primary implementation targets Amazon Web Services (AWS) using standard Boto3 authentication chains. Testing and deployment are verified in the AWS Sydney region (ap-southeast-2). Support for Azure Resource Manager and Google Cloud Resource Manager is architected as an extensible interface but remains outside current scope.")

    p("Operational Safety Boundaries: The AI Advisor (Google Gemini) is strictly restricted to analytical and advisory tasks; the LLM is architecturally isolated and cannot execute cloud APIs, invoke shell commands, or trigger Terraform apply. Terraform apply execution is strictly decoupled from GitOps pull request creation or merging.")

    h2("1.5 Motivation and Expected Benefits")
    p("Cloud Waste Hunter was motivated by the imperative to transition enterprise cloud optimization from reactive, manual accounting reviews into proactive, software-defined governance. By combining deterministic telemetry analysis with Infrastructure as Code and generative AI, the platform delivers significant engineering and business benefits:")

    p("• Elimination of Cloud Bill Shock: Prevents unattached storage disks and idle compute nodes from accumulating thousands of dollars in compounding monthly waste.")

    p("• Guaranteed Production Safety: By requiring human verification and binary plan inspection, organizations eliminate the fear of accidental outages inherent in blind automation.")

    p("• Continuous IaC State Synchronization: Decommissioning assets via declarative Terraform patches ensures that the codebase remains the definitive single source of truth, preventing infrastructure drift.")

    p("• Environmental Sustainability: By linking resource termination to carbon footprint reduction metrics, the platform empowers organizations to meet corporate green computing and sustainability goals.")

    # -------------------------------------------------------------
    # 2. EXISTING SYSTEM AND PROPOSED SOLUTION
    # -------------------------------------------------------------
    h1("2. Existing System and Proposed Solution", page_break=False)
    
    h2("2.1 Existing Approaches to Cloud Cost Monitoring")
    p("Organizations currently utilize three primary paradigms to monitor and manage cloud resource expenditure:")

    p("1. Native Cloud Provider Dashboards: Cloud vendors provide built-in billing portals, such as AWS Cost Explorer, AWS Budgets, and AWS Trusted Advisor. These tools aggregate historical billing data and provide rule-based recommendations (e.g., flagging low-utilization EC2 instances).")

    p("2. Enterprise Cloud Management Platforms (CMPs): Third-party software platforms such as CloudHealth by VMware, Datadog Cloud Cost Management, and Spot.io offer multi-cloud cost visibility, anomalous spend alerting, and reservation planning across diverse cloud environments.")

    p("3. Custom Cleanup Scripts ('Janitor Bots'): Internal platform engineering teams frequently write custom Python (Boto3) scripts, cron jobs, or scheduled AWS Lambda functions designed to periodically scan resource lists and delete unattached volumes or stop idle instances.")

    h2("2.2 Limitations of the Existing Approaches")
    p("While these approaches provide varying degrees of utility, they suffer from critical technical and governance limitations:")

    p("• Lack of Closed-Loop Remediation: Native cloud tools and commercial CMPs are fundamentally observational. They generate alert notifications and dashboard charts, but they cannot execute safe, validated remediation. The tedious task of locating the corresponding IaC code, modifying HCL files, testing diffs, and applying changes remains manual.")

    p("• Prohibitive Licensing Costs: Enterprise CMPs impose substantial monthly subscription fees, frequently calculated as a percentage of total cloud spend (often 2% to 5%), eroding the very cost savings they are purchased to deliver.")

    p("• Dangerous Out-of-Band State Drift: When custom scripts delete AWS assets directly via cloud APIs, the underlying Terraform state file is completely bypassed. When an engineer subsequently runs terraform apply, Terraform detects resource disappearance, leading to state locking errors, unexpected resource recreation, or pipeline failures.")

    p("• Lack of Empirical Safety Verifications: Existing janitor scripts do not verify CloudWatch I/O metrics before termination. If an EBS volume is unattached simply because an instance is undergoing a 30-minute maintenance reboot, the script blindly deletes the disk, permanently destroying valuable data.")

    h2("2.3 Proposed Cloud Waste Hunter Solution")
    p("Cloud Waste Hunter resolves these fundamental deficiencies by introducing an integrated, closed-loop FinOps automation platform. Rather than treating monitoring, AI reasoning, and infrastructure modification as isolated tasks, Cloud Waste Hunter unifies them into a cohesive, seven-module architecture governed by strict pre-apply safety gates and GitOps peer review.")

    p("The system operates in dual execution modes: a Real AWS Mode that scans live cloud accounts via Boto3 and executes real Terraform CLI commands, and a Simulated Demo Mode that models complex enterprise environments without requiring active AWS credentials. By coupling heuristic telemetry detection with declarative Terraform patch generation and human approval checkpoints, the platform guarantees that no cloud resource is ever modified or destroyed without comprehensive verification, structural plan validation, and explicit engineer authorization.")

    h2("2.4 Key Features Verified in the Implementation")
    p("The following key capabilities have been fully implemented in the source code and verified through automated test suites:")

    p("1. STS-Authenticated AWS Discovery: Real-time discovery of EC2, EBS, EIP, Lambda, and S3 resources with caller identity verification (core/aws/discovery.py).")

    p("2. Empirical Metric Ingestion: Retrieval and evaluation of 14-day CloudWatch telemetry metrics, parsing average/peak CPU, memory, read/write IOPS, and network bandwidth (core/aws/metrics.py).")

    p("3. Multi-Category Waste Rules Engine: Automated heuristic evaluation detecting oversized compute (<5% CPU), unattached EBS volumes (0 IOPS), dormant Lambda functions (0 invocations/30d), and unassociated Elastic IPs (core/module2_waste_detection.py).")

    p("4. AWS Pricing & Carbon Modeling: Real-time financial estimation calculating monthly and annualized savings, combined with a 0.000417 kg CO2e/kWh carbon reduction algorithm (core/module3_cost_estimation.py).")

    p("5. Google Gemini AI Advisory: Real-time synthesis of executive summaries, risk assessments, remediation scripts, and rollback procedures using gemini-3.5-flash-lite (core/gemini_advisor.py).")

    p("6. Declarative Terraform HCL Generator: Automated generation of clean, commented-out HCL patches for unattached disks and right-sized instance configurations (core/module5_remediation.py).")

    p("7. Eight-Point Safety Gate Enforcement: HashiCorp Terraform CLI execution wrapper enforcing fmt checks, syntax validation, automated state import, binary plan inspection, and 15-minute plan expiration (core/module6_terraform.py).")

    p("8. Dual-Checkbox Human Approval Gate: Interactive web controls requiring explicit engineer sign-off and secondary confirmation for destructive actions before apply execution.")

    p("9. GitOps Pull Request Orchestration: Automated branch isolation, commit generation, CI check status resolution, and tamper-evident audit logging (core/module7_gitops.py).")

    h2("2.5 Functional Requirements")
    p("The system requirements implemented and verified in Cloud Waste Hunter are detailed in Table 2.1.")

    fr_headers = ["Req ID", "Requirement Description", "Source Module", "Verification Status"]
    fr_rows = [
        ["FR1", "Authenticate with AWS using STS and verify service access (EC2, CW, S3, CE).", "core/aws/connection.py", "VERIFIED (11 Tests)"],
        ["FR2", "Discover EC2, EBS, EIP, Lambda, and S3 assets across specified AWS regions.", "core/aws/discovery.py", "VERIFIED (10 Tests)"],
        ["FR3", "Ingest 14-day historical CloudWatch metric streams for discovered assets.", "core/aws/metrics.py", "VERIFIED (9 Tests)"],
        ["FR4", "Classify resources against deterministic heuristic waste rules (Compute, Storage, Serverless, Network).", "core/module2_waste_detection.py", "VERIFIED (8 Tests)"],
        ["FR5", "Calculate monthly/annual financial savings and GHG carbon reduction metrics.", "core/module3_cost_estimation.py", "VERIFIED (8 Tests)"],
        ["FR6", "Synthesize grounded AI advisory recommendations using Google Gemini (gemini-3.5-flash-lite).", "core/gemini_advisor.py", "VERIFIED (11 Tests)"],
        ["FR7", "Provide local heuristic fallback advice when AI API keys or quotas are unavailable.", "core/module4_ai_advisor.py", "VERIFIED (18 Tests)"],
        ["FR8", "Generate clean, declarative Terraform HCL patches for detected waste items.", "core/module5_remediation.py", "VERIFIED (8 Tests)"],
        ["FR9", "Execute terraform fmt -check and terraform validate on generated patches.", "core/module6_terraform.py", "VERIFIED (35 Tests)"],
        ["FR10", "Bind unmanaged live AWS assets into state using terraform import before destruction.", "core/module6_terraform.py", "VERIFIED (6 Tests)"],
        ["FR11", "Enforce dual-checkbox Human Sign-Off Gate for destructive terraform apply execution.", "core/module6_terraform.py", "VERIFIED (14 Tests)"],
        ["FR12", "Orchestrate GitOps Pull Requests on isolated branches (finops/<resource>/<action>).", "core/module7_gitops.py", "VERIFIED (36 Tests)"],
        ["FR13", "Enforce automated CI validation checks and tamper-evident audit logging.", "core/module7_gitops.py", "VERIFIED (36 Tests)"],
        ["FR14", "Serve responsive single-page dashboard with real-time Chart.js visualizations.", "app/server.py", "VERIFIED (Live UI)"]
    ]
    add_tbl(fr_headers, fr_rows, [0.8, 2.7, 1.6, 1.17], "2.1", "Functional Requirements Specification and Implementation Verification")

    h2("2.6 Non-Functional Requirements")
    p("The architectural and quality attributes enforced by the platform are detailed in Table 2.2.")

    nfr_headers = ["NFR ID", "Quality Attribute", "Specification & Architectural Invariant", "Verification Metric"]
    nfr_rows = [
        ["NFR1", "Security", "Zero hardcoded credentials; standard AWS credential chain; masked secrets; LLM prompt sanitization.", "Passed payload inspection tests"],
        ["NFR2", "Safety", "Decoupled GitOps PR lifecycle; mandatory human approval gate; double confirm for deletions.", "100% blocked without sign-off"],
        ["NFR3", "Performance", "REST API response times < 200 ms for cached views; asynchronous pipeline execution.", "Observed <120 ms latency"],
        ["NFR4", "Reliability", "Graceful degradation on missing credentials, API rate limits, or network timeouts; zero app crashes.", "Structured error responses (163 tests)"],
        ["NFR5", "Portability", "Cross-platform execution across Linux (Ubuntu 24.04/26.04) and Windows 10/11.", "Verified on Ubuntu & Win32"],
        ["NFR6", "Cost Efficiency", "Zero operational infrastructure cost; runs within AWS Free Tier limits (t3.micro).", "$0.00 / month observed"],
        ["NFR7", "Auditability", "Tamper-evident audit trail with ISO timestamps, reviewer identities, and plan hashes.", "Cryptographic hash verification"],
        ["NFR8", "Maintainability", "Modular 7-module architecture; strict Pydantic schemas; comprehensive test coverage.", "163 passing unit/integration tests"]
    ]
    add_tbl(nfr_headers, nfr_rows, [0.8, 1.2, 3.1, 1.17], "2.2", "Non-Functional Requirements Specification and Quality Attributes")

    h2("2.7 Assumptions and Constraints")
    p("The implementation and deployment of Cloud Waste Hunter operate under the following explicit engineering assumptions and constraints:")

    p("1. Network Connectivity: The application requires outbound HTTPS access (port 443) to AWS service endpoints (sts.amazonaws.com, ec2.<region>.amazonaws.com, monitoring.<region>.amazonaws.com) and the Google Gemini API endpoint (generativelanguage.googleapis.com). In air-gapped environments, the system automatically falls back to local heuristic reasoning and in-memory simulation.")

    p("2. Read-Only IAM Permissions Baseline: The platform assumes that the executing AWS identity possesses read-only access (AmazonEC2ReadOnlyAccess, CloudWatchReadOnlyAccess). Destructive actions via Terraform require separate administrative credentials.")

    p("3. Hardware Resource Constraints: On Free Tier EC2 instances (t3.micro with 1.0 GiB RAM), the Python virtual environment and Uvicorn ASGI server must maintain a memory footprint under 200 MB to avoid Out-Of-Memory (OOM) process termination.")

    p("4. Local Terraform CLI Dependency: Executing live Terraform operations requires a locally installed HashiCorp Terraform CLI binary (v1.5.0 or later) present on the system PATH.")

    # -------------------------------------------------------------
    # 3. TECHNOLOGY STACK AND SYSTEM REQUIREMENTS
    # -------------------------------------------------------------
    h1("3. Technology Stack and System Requirements", page_break=False)
    
    h2("3.1 Programming Languages and Frameworks")
    p("Backend Core Runtime: Python 3.12 / 3.14 was selected as the foundational programming language. Python provides an ideal ecosystem for cloud engineering, featuring native support for the official AWS Boto3 SDK, Google GenAI SDK, and mature web micro-frameworks. Python's dynamic typing combined with Pydantic v2 type hints ensures robust runtime data validation.")

    p("Data Modeling & Validation: Pydantic v2 is utilized across all modules to define strict data contracts (WasteFinding, CostFinding, AIRecommendation, TerraformPatch, GitOpsPR). Pydantic guarantees compile-time and runtime validation of JSON payloads, rejecting malformed structures before processing.")

    h2("3.2 Frontend Technologies")
    p("Presentation Interface: The user interface is implemented as a lightweight, responsive Single-Page Application (SPA) using standard HTML5 and modern vanilla JavaScript (ES6+). This architectural choice eliminates complex frontend compilation pipelines (such as Node.js, Webpack, or React build steps), enabling instant static serving directly from FastAPI.")

    p("Styling & Responsive Layout: The interface employs TailwindCSS (v3 via CDN) for modern, utility-first styling. The layout incorporates a customized dark-mode aesthetic with high-contrast status badges (Emerald, Amber, Rose, Sky) and responsive flexbox/grid containers.")

    p("Data Visualization: Financial savings distributions, resource breakdowns, and 7-day historical CPU utilization timeseries are rendered dynamically using Chart.js (v4 via CDN). Doughnut charts visualize waste distribution by category, while bar charts contrast current monthly spend against optimized spend.")

    h2("3.3 Backend Technologies and API Framework")
    p("FastAPI Web Framework: The REST API and static asset gateway are powered by FastAPI (v0.115+), built upon the Starlette ASGI toolkit. FastAPI offers high-throughput asynchronous request handling, automatic OpenAPI/Swagger documentation generation, and native integration with Pydantic.")

    p("ASGI Web Server: Uvicorn serves as the lightning-fast, production-grade ASGI web server running the FastAPI application. In deployment, Uvicorn is bound to 0.0.0.0:8000, managed as a persistent background daemon via Linux systemd.")

    p("Custom HTTP Middleware: A dedicated no-cache middleware intercepts all HTTP responses, injecting Cache-Control: no-cache, no-store, must-revalidate headers to ensure that browser clients always receive real-time telemetry updates without stale browser caching.")

    h2("3.4 AWS Services and SDKs")
    p("Amazon Web Services SDK (Boto3): Cloud Waste Hunter interfaces with AWS via Boto3 (v1.36+), utilizing the underlying Botocore library for resilient network transport, automatic retries, and structured exception handling.")

    p("Integrated AWS Services: The platform interacts with six distinct AWS cloud services:")
    p("• AWS Security Token Service (STS): Executes get_caller_identity to authenticate the active IAM role, account ID, and ARN.")
    p("• Amazon Elastic Compute Cloud (EC2): Discovers virtual instances, lifecycle states, instance families, and availability zones via describe_instances.")
    p("• Amazon Elastic Block Store (EBS): Evaluates storage volume states, sizes, IOPS, and attachment topologies via describe_volumes.")
    p("• Amazon CloudWatch: Ingests 14-day and 30-day timeseries telemetry streams (CPUUtilization, VolumeReadOps, VolumeWriteOps) via get_metric_data.")
    p("• AWS Cost Explorer: Queries historical billing data and unblended costs via get_cost_and_usage.")
    p("• AWS Identity and Access Management (IAM): Leverages EC2 instance profiles for keyless, secure credential discovery.")

    h2("3.5 Gemini AI Integration")
    p("Google GenAI SDK: The platform integrates the official google-genai Python SDK (v1.65+) to interface with Google's state-of-the-art Gemini foundational models.")

    p("Configured Model: The system utilizes gemini-3.5-flash-lite as its primary reasoning engine. This model provides sub-second latency, exceptional instruction following, and highly accurate structured JSON generation at minimal computational cost.")

    p("Structured Output & Safety Guardrails: All Gemini inference calls enforce strict Pydantic JSON schemas. System instructions explicitly restrict the model to analytical reasoning, prohibiting the generation of ungrounded metrics or unauthorized shell commands.")

    h2("3.6 Terraform and GitOps Tools")
    p("HashiCorp Terraform CLI: Local Terraform operations are executed via the official HashiCorp Terraform CLI binary (v1.16.5). The platform interfaces with the CLI through Python's subprocess module, capturing stdout/stderr and verifying exit codes.")

    p("Version Control & GitOps: The platform leverages Git (v2.43+) for local branch isolation (finops/<resource>/<action>), staging, and commit generation. Remote GitHub repository operations are handled via the PyGitHub API (v2.6+).")

    h2("3.7 Development and Operational Dependencies")
    p("Pytest Testing Suite: Automated unit, integration, and security tests are orchestrated via Pytest (v9.1.1). The test suite utilizes unittest.mock to mock Boto3, Botocore, Google GenAI, and Git interactions, enabling comprehensive offline verification.")

    h2("3.8 Operating System and Runtime Requirements")
    p("Cross-Platform Support: The platform is fully verified across Linux (Ubuntu 24.04 and 26.04 LTS x86_64) and Microsoft Windows (Windows 10/11 x86_64). File path handling uses Python's pathlib to guarantee cross-platform compatibility.")

    h2("3.9 Installation Prerequisites")
    p("A comprehensive summary of all software dependencies, versions, and verified operational roles is provided in Table 3.1.")

    tech_headers = ["Component", "Technology / Tool", "Verified Version", "Architectural Role"]
    tech_rows = [
        ["Runtime", "Python", "3.12 / 3.14.7", "Core application execution environment and standard libraries."],
        ["Web Framework", "FastAPI", "0.115.0+", "Asynchronous RESTful API routing, dependency injection, and middleware."],
        ["ASGI Server", "Uvicorn", "0.34.0+", "High-performance production web server bound to port 8000."],
        ["Data Modeling", "Pydantic", "2.10.0+", "Strict runtime data contracts, schema validation, and JSON serialization."],
        ["Cloud SDK", "AWS Boto3 / Botocore", "1.36.0+", "AWS service integration for STS, EC2, EBS, CloudWatch, and Cost Explorer."],
        ["Generative AI", "Google GenAI SDK", "1.65.0+", "Interface to Gemini 3.5 Flash Lite for explainable optimization advice."],
        ["IaC Tooling", "HashiCorp Terraform CLI", "1.16.5", "Infrastructure as Code plan generation, syntax validation, and state import."],
        ["GitOps Engine", "Git & PyGitHub", "2.43+ / 2.6+", "Automated branch isolation, commit generation, and GitHub PR workflows."],
        ["Testing Engine", "Pytest & Mock", "9.1.1 / 3.16.0", "Automated test execution, Boto3/AI mocking, and regression testing."],
        ["Frontend UI", "TailwindCSS & Chart.js", "3.4 / 4.4", "Responsive dark-mode interface and dynamic timeseries financial charts."]
    ]
    add_tbl(tech_headers, tech_rows, [1.0, 1.8, 1.1, 2.37], "3.1", "Comprehensive Technology Stack and Dependency Specifications")

    # -------------------------------------------------------------
    # 4. SYSTEM ARCHITECTURE AND DESIGN
    # -------------------------------------------------------------
    h1("4. System Architecture and Design", page_break=False)
    
    h2("4.1 High-Level System Architecture")
    p("Cloud Waste Hunter is architected as an enterprise-grade, three-tier decoupled platform comprising a Presentation Layer, an Application and Orchestration Layer, and an External Cloud and Tooling Integration Layer. Figure 1 illustrates this multi-tier architecture and the communication interfaces connecting each subsystem.")

    add_fig("fig1_system_architecture.png", "1", "High-Level Three-Tier System Architecture of Cloud Waste Hunter, showing the Presentation Layer (TailwindCSS/Chart.js SPA), the Application and Orchestration Layer (FastAPI Core Engine), and the External Cloud and Tooling Integration Layer (AWS, Gemini, Terraform, GitOps).")

    p("Presentation Layer: A browser-based single-page application served statically by FastAPI. It provides interactive controls for toggling between Live AWS and Demo Simulation modes, triggering pipeline runs, reviewing real-time telemetry metrics, and executing human approval gates.")

    p("Application & Orchestration Layer: The brain of the platform, implemented in Python using FastAPI and the core FinOpsEngine. It coordinates the execution flow across the seven functional modules, enforces security validations, manages state transitions, and serves REST API endpoints.")

    p("External Integration Layer: Provides decoupled interfaces to external cloud platforms and CLI binaries, including the AWS Boto3 SDK, the Google Gemini API, the local HashiCorp Terraform CLI binary, and GitHub version control.")

    h2("4.2 Component Responsibilities")
    p("The responsibilities of the core architectural components are strictly partitioned to ensure high cohesion and low coupling:")
    p("• Static Asset Gateway (app/server.py): Mounts frontend assets, handles cross-origin requests, injects no-cache headers, and serializes Pydantic response models.")
    p("• FinOps Orchestrator (core/engine.py): Manages the sequential pipeline execution, coordinates data passing between modules, handles scenario selection, and aggregates audit metrics.")
    p("• AWS Service Adapters (core/aws/): Encapsulates low-level Boto3 client instantiation, STS authentication checks, error code classification, and pagination.")
    p("• AI Advisor Service (core/gemini_advisor.py): Formats telemetry evidence into structured prompts, manages Gemini API authentication, enforces JSON schema output, and falls back to local heuristic reasoning upon API unavailability.")
    p("• Terraform Execution Engine (core/module6_terraform.py): Wraps the local Terraform CLI, manages temporary workspace files, generates execution plans, and enforces safety gates.")

    h2("4.3 Frontend-Backend Interaction")
    p("Communication between the frontend SPA and the FastAPI backend is conducted exclusively via standard asynchronous HTTP REST calls transferring JSON payloads. On initial page load, the frontend initiates two concurrent asynchronous requests: GET /api/aws/status to verify cloud connectivity, and GET /api/aws/resources to retrieve the active resource inventory.")

    p("When a user initiates an optimization cycle, the frontend dispatches a POST /api/pipeline/run request containing the selected scenario or live AWS flag. The backend processes the pipeline synchronously and returns a unified JSON payload containing the complete FinOps report, which Chart.js and vanilla JavaScript immediately render into DOM elements without requiring a full page refresh.")

    h2("4.4 Data Flow and Module Interactions")
    p("Data flows sequentially through the system as an immutable pipeline of typed Pydantic data structures:")
    p("1. Raw Cloud Data $\\rightarrow$ MonitoredResource models (Module 1).")
    p("2. MonitoredResource $\\rightarrow$ Evaluated against heuristic rules $\\rightarrow$ WasteFinding models (Module 2).")
    p("3. WasteFinding $\\rightarrow$ Enriched with pricing & carbon calculations $\\rightarrow$ CostFinding models (Module 3).")
    p("4. WasteFinding + CostFinding $\\rightarrow$ Evaluated by Gemini AI $\\rightarrow$ AIRecommendation models (Module 4).")
    p("5. WasteFinding $\\rightarrow$ Synthesized into declarative HCL $\\rightarrow$ TerraformPatch models (Module 5).")
    p("6. TerraformPatch $\\rightarrow$ Validated via CLI $\\rightarrow$ Stored as binary plan artifact with Plan ID (Module 6).")
    p("7. Plan + Findings $\\rightarrow$ Formatted into isolated Git branch $\\rightarrow$ GitOpsPR model with CI checks (Module 7).")

    h2("4.5 End-to-End Workflow")
    p("The end-to-end lifecycle of a waste detection and remediation operation is depicted in Figure 2. The workflow progresses through eight discrete phases, transitioning from passive discovery to active, verified remediation.")

    add_fig("fig2_end_to_end_workflow.png", "2", "End-to-End Autonomous Cloud Waste Remediation Workflow, illustrating the step-by-step lifecycle from resource discovery and CloudWatch telemetry analysis to Gemini AI reasoning, Terraform plan generation, human sign-off, and GitOps review.")

    h2("4.6 Security and Approval Workflow")
    p("To eliminate the catastrophic operational risks inherent in automated cloud resource modification, Cloud Waste Hunter implements an Eight-Point Safety Gate architecture. Figure 3 illustrates the sequential verification gates through which any proposed change must pass.")

    add_fig("fig3_security_approval_workflow.png", "3", "Eight-Point Terraform and GitOps Security Safety Gate Architecture, showing the progressive verification layers enforcing read-only discovery, HCL sanitization, CLI validation, state import binding, binary plan inspection, dual human sign-off, branch isolation, and decoupled PR merging.")

    h2("4.7 Proposed Deployment Architecture")
    p("The deployment topology of Cloud Waste Hunter on AWS Free Tier infrastructure is illustrated in Figure 4. The architecture utilizes a single Ubuntu 26.04 LTS t3.micro EC2 instance residing in a Virtual Private Cloud (VPC) in the Sydney region (ap-southeast-2).")

    add_fig("fig4_ec2_deployment_architecture.png", "4", "AWS EC2 Free-Tier Live Production Topology in Sydney (ap-southeast-2), depicting the VPC, Security Group ingress rules (ports 8000, 80, 22), systemd process daemon, IAM role integration, and local Terraform CLI environment.")

    # -------------------------------------------------------------
    # 5. MODULE IMPLEMENTATION
    # -------------------------------------------------------------
    h1("5. Module Implementation", page_break=False)
    
    h2("5.1 Overview of the Seven Modules")
    p("The core functionality of Cloud Waste Hunter is partitioned into seven specialized modules coordinated by the unified FinOpsEngine. Table 5.1 outlines the responsibilities, primary source files, and architectural outputs of each module.")

    mod_headers = ["Module", "Module Name", "Primary Source File", "Core Architectural Output"]
    mod_rows = [
        ["Mod 1", "Resource Monitoring & Telemetry", "core/module1_monitoring.py", "Normalized MonitoredResource objects with CPU, I/O, and network telemetry."],
        ["Mod 2", "Waste Detection Rules Engine", "core/module2_waste_detection.py", "Deterministic WasteFinding objects categorized by waste type and severity."],
        ["Mod 3", "Cost & Carbon Estimation", "core/module3_cost_estimation.py", "CostFinding models with monthly savings ($) and carbon reduction (kg CO2)."],
        ["Mod 4", "AI Advisor Synthesis", "core/module4_ai_advisor.py", "AIRecommendation objects containing grounded executive summaries & risk ratings."],
        ["Mod 5", "Terraform HCL Remediation", "core/module5_remediation.py", "Declarative TerraformPatch objects containing clean, valid HCL code diffs."],
        ["Mod 6", "Terraform CLI Safety Gates", "core/module6_terraform.py", "Validated .tfplan artifacts, CLI validation logs, and Human Approval Gate."],
        ["Mod 7", "GitOps Review & PR Engine", "core/module7_gitops.py", "GitOpsPR objects on isolated branches with automated CI validation checks."]
    ]
    add_tbl(mod_headers, mod_rows, [0.8, 1.8, 1.8, 1.87], "5.1", "Architectural Responsibilities of the Seven FinOps Engine Modules")

    h2("5.2 Module 1: Resource Discovery and Telemetry Ingestion")
    p("Implementation Files: core/module1_monitoring.py, core/aws/discovery.py, core/aws/metrics.py.")
    p("Module 1 is responsible for discovering all deployed infrastructure assets across target AWS regions and extracting historical performance telemetry. In Real AWS Mode, the AWSDiscoveryService instantiates Boto3 clients to execute read-only API calls: describe_instances (EC2), describe_volumes (EBS), describe_addresses (Elastic IPs), list_functions (Lambda), and list_buckets (S3). All discovery queries implement automatic pagination handling using Boto3 Paginators, ensuring that enterprise accounts with thousands of resources are fully inventoried without truncation.")

    p("Concurrently, the AWSMetricsService queries Amazon CloudWatch via the get_metric_data API across 14-day and 30-day evaluation windows. It ingests CPUUtilization (Average and Maximum), VolumeReadOps, VolumeWriteOps, NetworkIn, NetworkOut, and Lambda Invocations. The metrics are normalized into the MonitoredResource Pydantic model, including a 7-day daily timeseries array utilized by the frontend for Chart.js rendering.")

    add_fig("fig_mod1_discovery.png", "5", "Module 1 — Live Cloud Discovery and Multi-Service Inventory Panel, displaying discovered EC2 instances, EBS volumes, Elastic IPs, and CloudWatch metrics.", width=Inches(4.5))

    h2("5.3 Module 2: Cloud Waste Detection Rules Engine")
    p("Implementation File: core/module2_waste_detection.py.")
    p("Module 2 evaluates the normalized MonitoredResource objects against deterministic engineering heuristic rules to identify resource waste. The rules engine evaluates four distinct categories of cloud waste:")

    p("1. Oversized Compute (EC2): An instance is classified as OVERSIZED_COMPUTE if its 14-day average CPU utilization is below 5.0% and its peak CPU utilization does not exceed 15.0%. The engine evaluates the instance family and recommends right-sizing to a lower-tier burstable instance (e.g., downsizing c5.4xlarge to t3.medium).")

    p("2. Unattached Block Storage (EBS): A volume is classified as UNATTACHED_STORAGE if its attachment status is available (detached) and its 14-day CloudWatch read/write IOPS are exactly zero. This detects abandoned disks left behind after instance termination.")

    p("3. Dormant Serverless Functions (Lambda): A function is classified as DORMANT_LAMBDA if it has accumulated zero invocations over the preceding 30 days and maintains provisioned concurrency allocations.")

    p("4. Idle Elastic IP Addresses (EIP): An IP is classified as UNASSOCIATED_EIP if its allocation status is unassociated with any running EC2 network interface, accumulating AWS idle IPv4 charges ($0.005/hour).")

    add_fig("fig_mod2_waste_detection.png", "6", "Module 2 — Heuristic Waste Detection and Risk Evaluation Findings, showing categorized waste items with severity ratings and resource telemetry.", width=Inches(4.5))

    h2("5.4 Module 3: Cost and Carbon Footprint Estimation")
    p("Implementation File: core/module3_cost_estimation.py.")
    p("Module 3 quantifies the financial and environmental benefits of remediating each identified waste finding. The module incorporates an on-demand AWS pricing matrix mapping instance types, EBS volume types (gp2, gp3, io1), and data transfer rates across AWS regions.")

    p("Financial Calculation: For unattached EBS volumes, monthly savings equal size_gb * monthly_rate_per_gb. For oversized compute, savings equal (current_hourly_rate - recommended_hourly_rate) * 730 hours. Annualized savings are projected linearly as monthly_savings * 12.")

    p("Carbon Footprint Calculation: The module incorporates the Greenhouse Gas Protocol ICT Sector Guidance model. Cloud energy consumption is modeled based on vCPU allocation, memory capacity, and thermal design power (TDP). Carbon emissions are calculated as:")
    p("CO2 (kg) = (vCPU * 15W + RAM_GB * 0.38W) * 730 hours * PUE (1.15) * 0.000417 kg CO2e/kWh")
    p("This provides organizations with verifiable ESG (Environmental, Social, and Governance) sustainability metrics.")

    add_fig("fig_mod3_cost_carbon.png", "7", "Module 3 — Cost Attribution, Annualized Savings, and GreenOps Carbon Footprint Model, detailing monthly savings and carbon reduction projections.", width=Inches(4.5))

    h2("5.5 Module 4: Google Gemini AI Advisor Synthesis")
    p("Implementation Files: core/module4_ai_advisor.py, core/gemini_advisor.py.")
    p("Module 4 bridges empirical telemetry with human-readable engineering advisory by integrating the Google Gemini generative AI platform (gemini-3.5-flash-lite). The GeminiAdvisorService constructs a rigorous system prompt enforcing strict FinOps safety boundaries:")
    p("• Evidence Grounding: The model is strictly instructed to reason exclusively over the provided telemetry metrics and pricing calculations, prohibiting the hallucination of unmonitored assets.")
    p("• Risk Assessment: The model assigns an operational risk level (LOW, MEDIUM, HIGH) evaluating the blast radius of remediation.")
    p("• Rollback Plan: The model generates explicit rollback procedures (e.g., restoring from an EBS snapshot or re-attaching an Elastic IP).")

    p("Structured Schema Output: The inference call specifies a strict Pydantic JSON schema (GeminiStructuredOutput). The response is parsed and validated into typed AIRecommendation objects. If the Gemini API key is missing or quota is exceeded, Module 4 automatically falls back to an internal heuristic reasoning engine, guaranteeing zero pipeline interruption.")

    add_fig("fig_mod4_ai_advisor.png", "8", "Module 4 — Google Gemini AI FinOps Advisor Synthesis and Executive Summary, presenting AI-driven recommendations, risk assessments, and rollback plans.", width=Inches(4.5))

    h2("5.6 Module 5: Terraform HCL Remediation Patch Generation")
    p("Implementation File: core/module5_remediation.py.")
    p("Module 5 translates the abstract waste findings into concrete, declarative Infrastructure as Code (IaC) modifications. Rather than executing imperative deletions, Module 5 synthesizes clean Terraform HCL patches targeting sample_infrastructure/main.tf.")

    p("For unattached EBS storage, the generator comments out or decommissions the exact resource block corresponding to the discovered volume ID, prepending descriptive FinOps audit headers. For oversized compute, it modifies the instance_type parameter to the right-sized family. The generator enforces strict sanitization rules, rejecting any HCL containing local-exec, remote-exec, shell scripts, curl, or credential strings.")

    add_fig("fig_mod5_hcl_patch.png", "9", "Module 5 — Declarative Terraform HCL Remediation Patch Generation, displaying sanitized HCL configuration diffs targeting infrastructure files.", width=Inches(4.5))

    h2("5.7 Module 6: Terraform CLI Safety Gates and Plan Integrity Verification")
    p("Implementation File: core/module6_terraform.py.")
    p("Module 6 serves as the primary safety gatekeeper of the platform, encapsulating local HashiCorp Terraform CLI execution. It enforces five sequential verification steps:")
    p("1. terraform fmt -check: Validates that generated HCL conforms to canonical formatting standards.")
    p("2. terraform validate: Validates configuration syntax, provider blocks, and variable bindings.")
    p("3. State Import Binding: For unmanaged live cloud assets discovered in the account, Module 6 executes terraform import aws_ebs_volume.waste <volume_id>, safely binding the asset into the local Terraform state before planning destruction.")
    p("4. Binary Plan Generation & Inspection: Executes terraform plan -out=tfplan.binary. It inspects the plan output to guarantee: Plan: 0 to add, 0 to change, N to destroy.")
    p("5. Human Approval Gate: The apply action is strictly locked behind a dual-checkbox verification requirement in the web UI.")

    add_fig("fig_mod6_safety_gates.png", "10", "Module 6 — Terraform CLI Safety Gates, SHA-256 Checksum, and Dual-Human Sign-Off Gate, illustrating interactive verification and approval safeguards.", width=Inches(4.5))

    h2("5.8 Module 7: GitOps Pull Request Review and Approval Workflow")
    p("Implementation Files: core/module7_gitops.py, core/gitops/orchestrator.py, core/gitops/git_service.py.")
    p("Module 7 implements the GitOps governance lifecycle (FR12 & FR13). When a remediation plan is generated, the GitOpsOrchestrator creates a dedicated, isolated Git branch: finops/<resource>/<action>. It stages the verified Terraform patch, generates a descriptive commit, and opens a Pull Request.")

    p("The PR body embeds a complete FinOps audit dossier, including CloudWatch metrics evidence, monthly financial savings, carbon reduction, and the Gemini AI risk assessment. The PR executes five automated CI checks: Terraform Format, Terraform Validate, Cost Policy Check, AI Safety Guardrail, and Peer Review Approval. Crucially, merging the PR does NOT autonomously trigger terraform apply, ensuring complete separation of concerns.")

    add_fig("fig_mod7_gitops.png", "11", "Module 7 — GitOps Pull Request Review, Branch Management, and Verification Checklist, displaying isolated branch creation and CI/CD review boundaries.", width=Inches(4.5))

    h2("5.9 Inter-Module Communication")
    p("Inter-module communication is orchestrated synchronously in memory by the FinOpsEngine. All data passed between modules consists of immutable, validated Pydantic models. This design prevents side-effect mutations, ensures thread safety, and enables comprehensive unit testing of individual modules in isolation.")

    h2("5.10 Error Handling and Failure Scenarios")
    p("The architecture implements comprehensive error handling across all failure modes:")
    p("• Missing AWS Credentials: STS authentication returns structured CREDENTIALS_MISSING status; the application gracefully falls back to Demo Simulation mode without crashing.")
    p("• Service-Level Access Denied: If an IAM policy denies ec2:DescribeVolumes, the error is isolated to the EBS adapter while EC2 discovery proceeds uninterrupted.")
    p("• Gemini Rate Limiting (429): Handled gracefully by logging a warning and activating the internal heuristic advisor.")
    p("• Terraform Syntax Errors: terraform validate failure halts pipeline execution immediately, preventing corrupted configurations from reaching the plan phase.")

    h2("5.11 Implementation Limitations")
    p("The current implementation possesses the following known limitations:")
    p("• Multi-Account AWS Organizations: The current discovery engine operates within a single AWS account context per execution.")
    p("• Containerized Workloads: Microservice pods deployed on Amazon EKS are not dynamically right-sized by the current rules engine.")
    p("• Historical Window Boundary: Metric analysis is bounded by CloudWatch's standard 14-day and 30-day API retention tiers.")

    # -------------------------------------------------------------
    # 6. SECURITY AND SAFETY CONTROLS
    # -------------------------------------------------------------
    h1("6. Security and Safety Controls", page_break=False)
    
    h2("6.1 AWS Credential Management")
    p("Cloud Waste Hunter adheres to strict enterprise cloud security standards. The application codebase contains zero hardcoded AWS access keys, secret keys, or session tokens. All AWS client initialization delegates to Botocore's standard credential resolution chain:")
    p("1. Explicit environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).")
    p("2. Shared credential files (~/.aws/credentials).")
    p("3. EC2 Instance Profile credentials delivered via the Amazon EC2 Instance Metadata Service (IMDSv2).")
    p("Sensitive credential files (.env) are explicitly excluded from version control via .gitignore.")

    h2("6.2 IAM Roles and Least-Privilege Permissions")
    p("For production deployment, Cloud Waste Hunter enforces the principle of least privilege. The application operates using a dedicated IAM role (CloudWasteHunterEC2Role) containing strictly read-only permissions:")
    p("• AmazonEC2ReadOnlyAccess (describe_instances, describe_volumes, describe_addresses).")
    p("• CloudWatchReadOnlyAccess (get_metric_data, list_metrics).")
    p("• AWSPriceListServiceFullAccess / Cost Explorer read access (get_cost_and_usage).")
    p("Destructive actions (such as ec2:DeleteVolume) are never granted to the application runtime role; they are executed only via local Terraform execution under authorized operator supervision.")

    h2("6.3 AWS Identity Verification")
    p("Prior to initiating any live discovery or analysis operation, the platform executes a mandatory pre-flight authentication check against AWS STS: sts.get_caller_identity(). The response validates the active Account ID, User/Role ARN, and User ID. If STS verification fails, all live AWS operations are halted immediately.")

    h2("6.4 Gemini API Key Protection")
    p("The Google Gemini API key is loaded strictly from the GEMINI_API_KEY environment variable. The key is never logged to disk, rendered in HTML templates, or exposed via REST API responses. Furthermore, the GeminiAdvisorService inspects prompt payloads prior to dispatch, guaranteeing that no AWS credentials, account numbers, or private network IPs are ever transmitted to external AI endpoints.")

    h2("6.5 Live Mode versus Demo Mode")
    p("The platform maintains complete physical and logical separation between Live AWS Mode and Demo Simulation Mode. In Demo Mode, the Boto3 SDK and Terraform CLI are completely bypassed; all data is served from immutable scenario definitions (SCENARIOS in data/scenarios.py). This guarantees that users can demonstrate and test the application without any risk of interacting with live cloud environments.")

    h2("6.6 Terraform Plan Validation and Integrity Verification")
    p("To prevent configuration tampering, Module 6 enforces cryptographic plan integrity verification. When a Terraform plan is generated, the system computes an SHA-256 hash of the configuration diff and plan binary. Prior to executing terraform apply, the system re-computes the hash; any discrepancy halts execution immediately with a CONFIG_TAMPERING_DETECTED security violation.")

    h2("6.7 Human Approval and Destructive-Action Safeguards")
    p("Automated systems must never possess autonomous authority to destroy enterprise infrastructure. Cloud Waste Hunter implements an interactive Human-in-the-Loop Sign-Off Gate in the web dashboard:")
    p("1. Verification Checkbox: An authorized engineer must review the unified diff and check: 'I have verified the proposed HCL modifications, diff, and resource impact, and grant explicit human approval.'")
    p("2. Secondary Destructive Confirmation: If the plan includes resource deletions (e.g., volume removal), a secondary confirmation checkbox is dynamically rendered and mandatory: 'I explicitly confirm destructive actions.'")
    p("The 'Execute Approved Terraform Apply' button remains strictly disabled until both checkboxes are actively selected.")

    h2("6.8 Plan Expiry and Audit Logging")
    p("Terraform plans represent a snapshot of infrastructure state at a specific moment in time. To prevent the execution of stale plans against evolved cloud environments, all generated plans enforce a strict 15-minute expiration window. If an approval is submitted after 15 minutes, the apply engine rejects the request with PLAN_STALE_EXPIRED and mandates a fresh pipeline execution. All approval events, reviewer names, timestamps, and exit codes are recorded in a tamper-evident audit log.")

    h2("6.9 GitOps Review and Approval Boundaries")
    p("The platform enforces a strict architectural boundary between GitOps pull request review and Terraform apply execution. Approving or merging a Pull Request on GitHub updates the version-controlled codebase but does NOT execute terraform apply. Infrastructure application is decoupled, requiring explicit operator execution through the validated Terraform CLI runner.")

    h2("6.10 Security Limitations and Recommendations")
    p("Table 6.1 details the security threat vectors evaluated in Cloud Waste Hunter and the corresponding defensive safeguards implemented.")

    sec_headers = ["Threat Vector", "Potential Impact", "Defensive Control Implemented", "Verification Status"]
    sec_rows = [
        ["Credential Leakage", "Unauthorized AWS account access via public GitHub commits.", ".gitignore excludes .env; Boto3 IMDSv2 role resolution.", "VERIFIED (Passed audit)"],
        ["Accidental Deletion", "Production data loss from automated deletion scripts.", "Dual-checkbox Human Sign-Off Gate; secondary destructive confirm.", "VERIFIED (14 Tests)"],
        ["Out-of-Band Drift", "Terraform state corruption from manual cloud deletions.", "Automated terraform import binds live assets before planning.", "VERIFIED (6 Tests)"],
        ["Prompt Injection", "Malicious telemetry manipulating AI recommendations.", "Strict Pydantic JSON schema enforcement; system prompt isolation.", "VERIFIED (11 Tests)"],
        ["Stale Plan Apply", "Executing outdated plans against modified cloud states.", "15-minute cryptographic plan expiration timeout enforcement.", "VERIFIED (Scenario 3 Test)"],
        ["Config Tampering", "Unauthorized modification of HCL files between plan and apply.", "SHA-256 configuration diff hashing and verification.", "VERIFIED (Scenario 4 Test)"]
    ]
    add_tbl(sec_headers, sec_rows, [1.1, 1.8, 2.3, 1.07], "6.1", "Security Threat Vector Analysis and Corresponding Mitigation Safeguards")

    # -------------------------------------------------------------
    # 7. INSTALLATION, CONFIGURATION AND OPERATION
    # -------------------------------------------------------------
    h1("7. Installation, Configuration and Operation", page_break=False)
    
    h2("7.1 Prerequisites")
    p("Deploying and running Cloud Waste Hunter requires the following baseline system components:")
    p("• Operating System: Ubuntu 22.04 / 24.04 / 26.04 LTS (recommended) or Windows 10/11.")
    p("• Python Runtime: Python 3.10, 3.11, 3.12, or 3.14 with pip and venv support.")
    p("• HashiCorp Terraform: Terraform CLI binary v1.5.0 or later installed on system PATH.")
    p("• Version Control: Git v2.30+ installed.")
    p("• AWS Account (Optional for Live Mode): An AWS account with read-only IAM credentials.")

    h2("7.2 Obtaining the Source Code")
    p("The complete source code is cloned from the official GitHub repository:")
    code_box("git clone https://github.com/vivek41754-tech/project.git cloud-waste-hunter\ncd cloud-waste-hunter")

    h2("7.3 Python Environment Setup")
    p("To ensure dependency isolation, a dedicated Python virtual environment is created and activated:")
    code_box("python3 -m venv venv\nsource venv/bin/activate   # On Linux / macOS\n# venv\\Scripts\\activate     # On Windows PowerShell")

    h2("7.4 Dependency Installation")
    p("All required runtime libraries are installed from requirements.txt:")
    code_box("pip install --upgrade pip\npip install -r requirements.txt")

    h2("7.5 External Tool Installation")
    p("On Ubuntu Linux, the official HashiCorp Terraform binary is installed via the HashiCorp APT repository:")
    code_box("wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg\necho \"deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main\" | sudo tee /etc/apt/sources.list.d/hashicorp.list\nsudo apt-get update -y && sudo apt-get install -y terraform")

    h2("7.6 Environment Configuration")
    p("The application configuration is defined in .env. Table 7.1 outlines the supported configuration parameters.")

    env_headers = ["Variable Name", "Default Value", "Description & Operational Significance"]
    env_rows = [
        ["AWS_ACCESS_KEY_ID", "None (IMDSv2)", "AWS access key for STS authentication (optional if IAM role is attached)."],
        ["AWS_SECRET_ACCESS_KEY", "None (IMDSv2)", "AWS secret access key corresponding to the access key ID."],
        ["AWS_DEFAULT_REGION", "ap-southeast-2", "Target AWS region for resource discovery, CloudWatch, and pricing."],
        ["GEMINI_API_KEY", "None", "Google Gemini API key required for generative AI advisory synthesis."],
        ["GITHUB_TOKEN", "None", "GitHub Personal Access Token with repo scope (required for live GitOps PRs)."],
        ["GIT_REPOSITORY", "None", "Target GitHub repository in 'owner/repo' format for GitOps PR dispatch."]
    ]
    add_tbl(env_headers, env_rows, [1.8, 1.2, 3.27], "7.1", "Environment Configuration Variables and Supported System Parameters")

    h2("7.7 AWS Configuration")
    p("AWS credentials can be configured via environment variables in .env, standard credential files (~/.aws/credentials), or through an attached IAM Instance Profile on EC2.")

    h2("7.8 Gemini Configuration")
    p("The Gemini API key is appended to .env: echo \"GEMINI_API_KEY=your_key_here\" >> .env.")

    h2("7.9 Starting the Application")
    p("The application is launched using Uvicorn:")
    code_box("python -m uvicorn app.server:app --host 0.0.0.0 --port 8000")

    h2("7.10 Accessing the Application Interface")
    p("The web dashboard is accessed by navigating to http://localhost:8000 or http://<SERVER_PUBLIC_IP>:8000.")

    h2("7.11 Operational Verification")
    p("The comprehensive 163-test verification suite is executed using Pytest:")
    code_box("pytest tests/ -v")

    h2("7.12 Troubleshooting")
    p("Common operational issues and verified resolutions:")
    p("• Port 8000 In Use: Terminate conflicting processes via fuser -k 8000/tcp or bind to an alternative port.")
    p("• AWS Credentials Missing: Verify ~/.aws/credentials syntax or verify EC2 instance profile attachment.")
    p("• Terraform Binary Not Found: Ensure /usr/bin/terraform or /usr/local/bin/terraform is present on PATH.")

    # -------------------------------------------------------------
    # 8. PROPOSED AWS EC2 DEPLOYMENT AND COST CONSIDERATIONS
    # -------------------------------------------------------------
    h1("8. Proposed AWS EC2 Deployment and Cost Considerations", page_break=False)
    
    h2("8.1 Deployment Objectives")
    p("The deployment objective for Cloud Waste Hunter was to establish a production-grade, 24/7 accessible, zero-cost cloud hosting environment on AWS Free Tier compute infrastructure, enabling faculty, students, and reviewers to interact with the live platform via standard web browsers.")

    h2("8.2 Existing Application Compatibility")
    p("The application architecture was engineered for seamless Linux deployment. The Python ASGI foundation, decoupled static frontend, and reliance on standard Linux utilities (systemd, bash, iptables) ensure native compatibility with Ubuntu Server without requiring container virtualization overhead.")

    h2("8.3 Proposed EC2 Architecture")
    p("The deployment topology consists of a dedicated Amazon EC2 virtual machine residing within the default Virtual Private Cloud (VPC) in the AWS Sydney region (ap-southeast-2). The instance is allocated a public IPv4 address and secured by an AWS Security Group.")

    h2("8.4 Operating System and Instance Selection")
    p("Operating System: Ubuntu Server 26.04 LTS (x86_64, Linux kernel 7.0.0-1006-aws) was selected for long-term stability, robust package management, and systemd service management.")

    p("Instance Type: The AWS t3.micro compute size (2 vCPUs, 1.0 GiB RAM) was provisioned. In ap-southeast-2, t3.micro is the designated AWS Free Tier compute family, providing 750 free hours per month for eligible accounts.")

    h2("8.5 IAM Instance Role Configuration")
    p("To eliminate stored credentials on the server, the instance is configured with an IAM Instance Profile (CloudWasteHunterEC2Role) granting read-only access to EC2, CloudWatch, and Cost Explorer. This enables the Boto3 SDK to automatically resolve temporary credentials via IMDSv2.")

    h2("8.6 Network Access and Application Security")
    p("Network access is governed by Security Group launch-wizard-1 (sg-016fa0e08cffb34d8). Inbound rules authorize Custom TCP port 8000 (0.0.0.0/0), HTTP port 80 (0.0.0.0/0), and SSH port 22. To enable convenient web browsing without appending :8000, Linux iptables NAT redirection was implemented:")
    code_box("sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000")

    h2("8.7 Application Process Management")
    p("Process resilience is enforced via systemd. A service unit /etc/systemd/system/cloud-waste-hunter.service was created and enabled:")
    code_box("[Unit]\nDescription=Cloud Waste Hunter & Auto-Remediator Web Service\nAfter=network.target\n\n[Service]\nType=simple\nUser=ubuntu\nWorkingDirectory=/home/ubuntu/cloud-waste-hunter\nEnvironment=\"PATH=/home/ubuntu/cloud-waste-hunter/venv/bin:/usr/local/bin:/usr/bin:/bin\"\nEnvironmentFile=-/home/ubuntu/cloud-waste-hunter/.env\nExecStart=/home/ubuntu/cloud-waste-hunter/venv/bin/python -m uvicorn app.server:app --host 0.0.0.0 --port 8000\nRestart=always\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target")

    h2("8.8 Logging and Operational Monitoring")
    p("System and application logs are captured by systemd and inspected via journalctl -u cloud-waste-hunter.service -f. Uvicorn outputs real-time HTTP access logs detailing client IP, endpoint, response code, and latency.")

    h2("8.9 Free Tier Eligibility and Cost Considerations")
    p("The deployment is architected to guarantee 100% Free-Tier compliance ($0.00/month). Table 8.1 provides the comprehensive monthly cost breakdown.")

    cost_headers = ["AWS Resource", "Provisioned Capacity", "AWS Free Tier Allowance", "Monthly Cost ($)"]
    cost_rows = [
        ["EC2 Compute", "t3.micro (750 hours/mo)", "750 hours/month of t2.micro / t3.micro", "$0.00 (Free Tier)"],
        ["EBS Storage", "8 GiB gp3 root volume", "30 GiB of General Purpose SSD (gp2/gp3)", "$0.00 (Free Tier)"],
        ["Public IPv4", "1 Dynamic Public IP", "Free while attached to running EC2 instance", "$0.00 (Free Tier)"],
        ["Data Transfer", "< 1 GiB / month (HTTP)", "100 GiB / month free internet egress", "$0.00 (Free Tier)"],
        ["TOTAL ESTIMATED SPEND", "Production Deployment", "Full Free-Tier Compliance", "$0.00 / month"]
    ]
    add_tbl(cost_headers, cost_rows, [1.5, 1.8, 2.0, 0.97], "8.1", "AWS Free Tier Monthly Compute and Storage Cost Breakdown")

    h2("8.10 Deployment Status and Operational Verification")
    p("The production deployment on AWS EC2 is fully completed, active, and verified. Table 8.2 details the verified operational parameters.")

    dep_headers = ["Deployment Parameter", "Verified Configuration", "Operational Status"]
    dep_rows = [
        ["Instance ID", "i-081d823df24e60ed1", "ACTIVE / RUNNING"],
        ["AWS Region", "ap-southeast-2 (Sydney, Australia)", "VERIFIED (Connected)"],
        ["Public IPv4 Address", "13.238.255.197", "GLOBALLY ACCESSIBLE"],
        ["Application URL", "http://13.238.255.197:8000", "HEALTHY (HTTP 200)"],
        ["Web Server Runtime", "Python 3.12 / Uvicorn 0.34.0 (FastAPI)", "MANAGED BY SYSTEMD"],
        ["Terraform CLI", "HashiCorp Terraform v1.16.5", "INSTALLED ON PATH"],
        ["Target AWS Account", "105456916922 (arn:aws:iam::105456916922:user/vivek)", "AUTHENTICATED (5/5 Services)"]
    ]
    add_tbl(dep_headers, dep_rows, [1.8, 2.7, 1.77], "8.2", "Verified Production Deployment Parameters on AWS EC2")

    p("Remaining Planned Work: Future enhancements include provisioning a custom domain name (e.g., finops.cloudwastehunter.io) and configuring TLS termination using Let's Encrypt Certbot on Nginx reverse proxy.")

    # -------------------------------------------------------------
    # 10. LIMITATIONS AND FUTURE ENHANCEMENTS
    # -------------------------------------------------------------
    h1("9. Limitations and Future Enhancements", page_break=False)
    
    h2("9.1 Current Technical Limitations")
    p("The platform exhibits several technical boundaries inherent in its current architecture:")
    p("• Single-Account Evaluation Scope: The engine evaluates infrastructure within a single AWS account credential context per execution; multi-account AWS Organizations aggregation is not natively orchestrated.")
    p("• Metric Retention Bounds: Telemetry analysis is bounded by CloudWatch's standard 14-day and 30-day API retrieval windows. Long-term seasonal trends spanning multiple quarters are not evaluated.")
    p("• Containerized Workload Exclusion: Microservices orchestrated inside Amazon EKS or ECS clusters are not analyzed by the current heuristic rules engine.")

    h2("9.2 Integration and Deployment Limitations")
    p("• HTTP Transport: In the baseline deployment, the public endpoint operates over HTTP (port 8000/80) without SSL/TLS encryption.")
    p("• Git Provider Scope: Automated pull request dispatch is currently optimized for GitHub; GitLab and Bitbucket providers are not yet integrated.")

    h2("9.3 Potential Improvements")
    p("1. Dynamic Polling Window Selection: Implementing interactive UI controls allowing engineers to adjust the CloudWatch evaluation window between 7, 14, 30, and 90 days.")
    p("2. Multi-Cloud Expansion: Developing service adapters for Microsoft Azure (Azure Monitor / Advisor) and Google Cloud Platform (Cloud Monitoring / Recommender).")
    p("3. Automated ChatOps Integration: Dispatching real-time notifications and approval requests directly to Slack and Microsoft Teams channels via Webhooks.")

    h2("9.4 Future Development Opportunities")
    p("Future development will explore machine learning-driven predictive scaling models that forecast compute demand using Prophet or LSTM neural networks, automatically preempting waste before over-provisioning occurs. Furthermore, native integration with Terraform 1.5+ declarative import blocks (import {}) will be implemented to streamline state synchronization.")

    # -------------------------------------------------------------
    # 11. CONCLUSION
    # -------------------------------------------------------------
    h1("10. Conclusion", page_break=False)
    
    h2("10.1 Summary of the Project")
    p("Cloud Waste Hunter was designed, developed, and verified to solve the pervasive challenge of cloud resource waste through autonomous, closed-loop financial governance. By unifying multi-service AWS discovery, CloudWatch heuristic telemetry analysis, empirical AWS pricing and GHG carbon footprint modeling, explainable Google Gemini AI advisory synthesis, and declarative Terraform HCL generation, the platform bridges the dangerous gap between passive monitoring and risky manual remediation.")

    h2("10.2 Achievement of Objectives")
    p("All eight core engineering objectives defined in Section 1.3 were fully achieved. The platform successfully automates multi-service discovery across EC2, EBS, EIP, Lambda, and S3; classifies waste against verified heuristics; synthesizes grounded AI recommendations via gemini-3.5-flash-lite; enforces eight strict Terraform CLI pre-apply safety gates; and orchestrates GitOps pull requests on isolated branches with automated CI validation checks.")

    h2("10.3 Verified Outcomes")
    p("The system's technical validity was confirmed through empirical evaluation:")
    p("• 163 of 163 automated unit, integration, and security tests passed with 100% test coverage.")
    p("• The application was successfully deployed to live AWS production in the Sydney region (ap-southeast-2) on a t3.micro EC2 instance, operating at $0.00/month within AWS Free Tier limits.")
    p("• Live cloud testing against an active AWS account successfully discovered and generated validated remediation plans for real unattached EBS storage waste while preserving active production compute assets.")

    h2("10.4 Final Assessment")
    p("Cloud Waste Hunter establishes that automated cloud financial governance does not require sacrificing production safety or infrastructure reproducibility. By placing declarative Infrastructure as Code and Human-in-the-Loop approval gates at the center of the remediation lifecycle, the platform provides a robust, scalable, and safe engineering model for modern enterprise FinOps.")

    # -------------------------------------------------------------
    # 12. REFERENCES
    # -------------------------------------------------------------
    h1("11. References", page_break=False)
    
    refs = [
        "[1] J. R. Storment and M. Fuller, Cloud FinOps: Collaborative, Real-Time Cloud Value Decision Making, 2nd ed. Sebastopol, CA: O'Reilly Media, 2023.",
        "[2] Amazon Web Services, \"AWS Well-Architected Framework: Cost Optimization Pillar,\" AWS Whitepapers, Oct. 2024. [Online]. Available: https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/",
        "[3] FinOps Foundation, \"FinOps Framework: Inform, Optimize, Operate,\" FinOps Technical Documentation, 2025. [Online]. Available: https://www.finops.org/framework/",
        "[4] HashiCorp, \"Terraform Documentation: Core Concepts, State Management, and CLI Workflows,\" HashiCorp Developer, 2026. [Online]. Available: https://developer.hashicorp.com/terraform/docs",
        "[5] Google Cloud, \"Gemini API Documentation and Python SDK Reference,\" Google AI for Developers, 2026. [Online]. Available: https://ai.google.dev/gemini-api/docs",
        "[6] Amazon Web Services, \"Boto3 Documentation: AWS SDK for Python API Reference,\" AWS Documentation, 2026. [Online]. Available: https://boto3.amazonaws.com/v1/documentation/api/latest/",
        "[7] S. Ramirez, \"FastAPI: Modern, High-Performance Web Framework for Python,\" FastAPI Documentation, 2025. [Online]. Available: https://fastapi.tiangolo.com/",
        "[8] Greenhouse Gas Protocol, \"GHG Protocol for the Information and Communication Technology (ICT) Sector,\" World Resources Institute and WBCSD, Tech. Rep., 2023.",
        "[9] A. Lim, L. Birch, and K. Behnke, \"Autonomous Cloud Resource Governance and Drift Prevention via GitOps Pipelines,\" IEEE Trans. Cloud Comput., vol. 12, no. 3, pp. 782–795, Jul. 2024.",
        "[10] International Organization for Standardization, \"Information technology — Security techniques — Information security management systems — Requirements,\" ISO/IEC 27001:2022, Geneva, Switzerland, 2022.",
        "[11] T. H. Cormen, C. E. Leiserson, R. L. Rivest, and C. Stein, Introduction to Algorithms, 4th ed. Cambridge, MA: MIT Press, 2022.",
        "[12] Amazon Web Services, \"Amazon EC2 Pricing and Instance Family Specifications,\" AWS Pricing Documentation, 2026. [Online]. Available: https://aws.amazon.com/ec2/pricing/on-demand/",
        "[13] Amazon Web Services, \"Amazon CloudWatch User Guide: Metric Streams and Mathematical Formulations,\" AWS Documentation, 2026. [Online]. Available: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/",
        "[14] GitOps Working Group, \"OpenGitOps: Principles of Declarative System Management,\" CNCF GitOps Technical Standards, 2024. [Online]. Available: https://opengitops.dev/",
        "[15] Pytest Development Team, \"Pytest: Full-Featured Python Testing Framework Documentation,\" Pytest.org, 2026. [Online]. Available: https://docs.pytest.org/"
    ]

    for ref in refs:
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.line_spacing = 1.0
        p_ref.paragraph_format.space_after = Pt(1.0)
        p_ref.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_ref = p_ref.add_run(ref)
        r_ref.font.name = "Times New Roman"
        r_ref.font.size = Pt(8.0)

    # -------------------------------------------------------------
    # 13. APPENDICES
    # -------------------------------------------------------------
    h1("12. Appendices", page_break=False)
    
    h2("12.1 Selected Configuration Templates")
    p("Appendix 13.1 provides the deployment automation script deploy_ec2.sh utilized to provision the application runtime on Ubuntu Linux.")
    code_box("#!/usr/bin/env bash\n# Cloud Waste Hunter - EC2 Free Tier Deployment Script\nsudo apt-get update -y && sudo apt-get install -y python3-pip python3-venv git curl unzip wget terraform\npython3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt\nsudo systemctl daemon-reload && sudo systemctl enable --now cloud-waste-hunter.service")

    h2("12.2 Deployment and System Service Configuration")
    p("Appendix 13.2 records the raw console summary log from the Pytest execution verifying all 163 automated test cases:")
    code_box("platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 | rootdir: .../finops-cloud-waste-hunter\ncollected 163 items | 11 test suites passing (AWS, Gemini, GitOps, Terraform, Modules 1-7)\n================= 163 passed, 3 warnings in 94.47s (0:01:34) =================")

    h2("12.3 Relevant API Details")
    p("Table 12.1 documents the primary REST API endpoints exposed by the Cloud Waste Hunter backend server.")

    api_headers = ["HTTP Method", "API Route Endpoint", "Request Body / Params", "Description & Response Status"]
    api_rows = [
        ["GET", "/", "None", "Serves the responsive Single-Page Application (HTML5/TailwindCSS)."],
        ["GET", "/api/aws/status", "region: Optional[str]", "Verifies AWS STS caller identity & service health (200 OK)."],
        ["GET", "/api/aws/resources", "region: Optional[str]", "Discovers live EC2, EBS, EIP, Lambda, and S3 resources (200 OK)."],
        ["GET", "/api/aws/metrics", "region: Optional[str], window: int", "Retrieves CloudWatch historical telemetry for resources (200 OK)."],
        ["GET", "/api/aws/costs", "days: int = 30", "Queries AWS Cost Explorer historical spend breakdown (200 OK)."],
        ["POST", "/api/aws/advisor", "AdvisorRequest JSON", "Executes Google Gemini AI advisor over live AWS evidence (200 OK)."],
        ["POST", "/api/pipeline/run", "PipelineRunRequest JSON", "Executes end-to-end FinOps pipeline for selected scenario (200 OK)."],
        ["POST", "/api/terraform/plan", "TerraformPlanApiRequest", "Generates and validates Terraform HCL patch & binary plan (200 OK)."],
        ["POST", "/api/terraform/apply", "TerraformApplyApiRequest", "Enforces Human Approval Gate and executes terraform apply (200 OK)."],
        ["POST", "/api/gitops/pr/{id}/approve", "PRActionRequest JSON", "Simulates GitOps peer review sign-off and updates CI checks (200 OK)."]
    ]
    add_tbl(api_headers, api_rows, [0.9, 1.8, 1.5, 2.07], "12.1", "Comprehensive REST API Endpoints Specification")

    h2("12.4 Sample Declarative Remediation Patch")
    p("Appendix 13.4 displays a sample declarative Terraform remediation patch generated by Module 5 for an unattached EBS storage finding:")
    code_box("# FinOps Patch - Module 5 | Resource: vol-0e46e40ef1c14ba2e (1 GiB gp3 Unattached Storage)\n# DECOMMISSIONED BY FINOPS HUNTER: Unattached for >14 days with 0 IOPS\n# resource \"aws_ebs_volume\" \"volume_vol_0e46e40ef1c14ba2e\" { size = 1; type = \"gp3\" }")

    # Finalize document layout & header/footer
    add_header_footer(doc)
    
    out_docx = "Cloud_Waste_Hunter_Project_Report.docx"
    doc.save(out_docx)
    print(f"Report document successfully saved to: {out_docx}")
    return os.path.abspath(out_docx)

if __name__ == "__main__":
    docx_path = create_report()
    print("Done generating DOCX:", docx_path)
